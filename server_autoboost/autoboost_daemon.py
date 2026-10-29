#!/usr/bin/env python3
"""
AutoBoost Daemon for Linux Servers
Lightweight, zero-dependency background service that monitors RAM and CPU,
automatically frees page/buffer cache, defragments memory, flushes DNS caches,
vacuums oversized system journals, and tames runaway background CPU hogs.

Modeled after Windows AutoBoost.
"""

import os
import sys
import time
import signal
import subprocess
import configparser
import logging
from typing import Dict, Tuple, List, Set

CONFIG_PATH = "/etc/autoboost/autoboost.conf"
LOG_PATH = "/var/log/autoboost.log"
STATE_FILE = "/run/autoboost.state"

DEFAULT_CONFIG = """[autoboost]
ram_threshold_percent = 85
cpu_threshold_percent = 90
check_interval_seconds = 5
cooldown_seconds = 30

drop_caches = true
compact_memory = true
flush_dns = true
vacuum_journal = true
max_journal_size = 100M
renice_cpu_hogs = true
cpu_hog_threshold = 30.0

protected_processes = systemd,kthreadd,sshd,mariadbd,mysqld,nginx,httpd,dockerd,containerd,docker-proxy,amazon-ssm-agent,systemd-journald,systemd-resolved,systemd-udevd,dbus-broker,n8n,node,python,python3,pm2,autoboost
"""

class AutoBoostDaemon:
    def __init__(self, config_file: str = CONFIG_PATH):
        self.config_file = config_file
        self.running = True
        self.last_boost_time = 0.0
        self.prev_cpu_times = None

        self.load_config()
        self.setup_logging()

    def load_config(self):
        config = configparser.ConfigParser()
        if os.path.exists(self.config_file):
            config.read(self.config_file)
        else:
            config.read_string(DEFAULT_CONFIG)

        sec = config["autoboost"] if "autoboost" in config else config["DEFAULT"]
        self.ram_threshold = sec.getint("ram_threshold_percent", 85)
        self.cpu_threshold = sec.getint("cpu_threshold_percent", 90)
        self.interval = sec.getint("check_interval_seconds", 5)
        self.cooldown = sec.getint("cooldown_seconds", 30)

        self.do_drop_caches = sec.getboolean("drop_caches", True)
        self.do_compact_memory = sec.getboolean("compact_memory", True)
        self.do_flush_dns = sec.getboolean("flush_dns", True)
        self.do_vacuum_journal = sec.getboolean("vacuum_journal", True)
        self.max_journal_size = sec.get("max_journal_size", "100M")
        self.do_renice = sec.getboolean("renice_cpu_hogs", True)
        self.cpu_hog_threshold = sec.getfloat("cpu_hog_threshold", 30.0)

        raw_protected = sec.get("protected_processes", "")
        self.protected_processes = {p.strip().lower() for p in raw_protected.split(",") if p.strip()}

    def setup_logging(self):
        log_dir = os.path.dirname(LOG_PATH)
        if not os.path.exists(log_dir):
            try:
                os.makedirs(log_dir, exist_ok=True)
            except Exception:
                pass

        logging.basicConfig(
            filename=LOG_PATH,
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        self.logger = logging.getLogger("AutoBoost")

    def get_memory_info(self) -> Dict[str, int]:
        """Reads /proc/meminfo and returns values in KB."""
        mem = {}
        try:
            with open("/proc/meminfo", "r") as f:
                for line in f:
                    parts = line.split(":")
                    if len(parts) == 2:
                        key = parts[0].strip()
                        val_str = parts[1].strip().split()[0]
                        mem[key] = int(val_str)
        except Exception as e:
            self.logger.error(f"Error reading /proc/meminfo: {e}")
        return mem

    def get_memory_usage(self) -> Tuple[float, int, int, int]:
        """Returns (used_percent, total_mb, available_mb, buff_cache_mb)."""
        mem = self.get_memory_info()
        total_kb = mem.get("MemTotal", 1)
        avail_kb = mem.get("MemAvailable", mem.get("MemFree", 0))
        buffers_kb = mem.get("Buffers", 0)
        cached_kb = mem.get("Cached", 0)
        buff_cache_kb = buffers_kb + cached_kb

        used_kb = total_kb - avail_kb
        used_percent = (used_kb / total_kb) * 100.0

        return (
            round(used_percent, 1),
            total_kb // 1024,
            avail_kb // 1024,
            buff_cache_kb // 1024
        )

    def get_cpu_usage(self) -> float:
        """Calculates global CPU usage percentage since last check via /proc/stat."""
        try:
            with open("/proc/stat", "r") as f:
                first_line = f.readline()
            
            # Line format: cpu  user nice system idle iowait irq softirq steal guest guest_nice
            fields = [int(x) for x in first_line.split()[1:]]
            idle_time = fields[3] + (fields[4] if len(fields) > 4 else 0)
            total_time = sum(fields)

            if self.prev_cpu_times is None:
                self.prev_cpu_times = (idle_time, total_time)
                return 0.0

            prev_idle, prev_total = self.prev_cpu_times
            self.prev_cpu_times = (idle_time, total_time)

            delta_idle = idle_time - prev_idle
            delta_total = total_time - prev_total

            if delta_total <= 0:
                return 0.0

            cpu_percent = (1.0 - (delta_idle / delta_total)) * 100.0
            return max(0.0, min(100.0, round(cpu_percent, 1)))
        except Exception as e:
            self.logger.error(f"Error reading /proc/stat: {e}")
            return 0.0

    def boost_memory(self) -> Dict[str, str]:
        """Executes system memory optimization actions."""
        results = {}
        
        # 1. Sync filesystems
        try:
            subprocess.run(["sync"], check=False)
            results["sync"] = "OK"
        except Exception as e:
            results["sync"] = f"Failed: {e}"

        # 2. Drop clean caches (pagecache, dentries, inodes)
        if self.do_drop_caches:
            try:
                with open("/proc/sys/vm/drop_caches", "w") as f:
                    f.write("3\n")
                results["drop_caches"] = "Freed pagecache and inodes"
            except PermissionError:
                results["drop_caches"] = "Skipped (Container host-managed)"
            except Exception as e:
                results["drop_caches"] = f"Failed: {e}"

        # 3. Compact memory
        if self.do_compact_memory:
            try:
                compact_path = "/proc/sys/vm/compact_memory"
                if os.path.exists(compact_path):
                    with open(compact_path, "w") as f:
                        f.write("1\n")
                    results["compact_memory"] = "Memory defragmented"
            except PermissionError:
                results["compact_memory"] = "Skipped (Container host-managed)"
            except Exception as e:
                results["compact_memory"] = f"Failed: {e}"

        # 4. Flush DNS resolver cache
        if self.do_flush_dns:
            flushed = False
            for cmd in [
                ["resolvectl", "flush-caches"],
                ["systemd-resolve", "--flush-caches"],
                ["systemctl", "reload", "nscd"]
            ]:
                try:
                    res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    if res.returncode == 0:
                        flushed = True
                        break
                except (FileNotFoundError, PermissionError):
                    continue
            results["dns_flush"] = "DNS cache flushed" if flushed else "Skipped/Not applicable"

        # 5. Vacuum journal if bloated
        if self.do_vacuum_journal:
            try:
                subprocess.run(
                    ["journalctl", f"--vacuum-size={self.max_journal_size}"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False
                )
                results["journal_vacuum"] = f"Vacuumed to {self.max_journal_size}"
            except Exception as e:
                results["journal_vacuum"] = f"Failed: {e}"

        # 6. Docker builder cache cleanup if docker is available
        try:
            res = subprocess.run(
                ["docker", "builder", "prune", "-f", "--reserved-space", "500M"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False
            )
            if res.returncode == 0:
                results["docker_prune"] = "Pruned build cache"
        except (FileNotFoundError, PermissionError):
            pass

        return results

    def tame_cpu_hogs(self) -> List[str]:
        """Identifies runaway background processes and renices them to lower priority."""
        if not self.do_renice:
            return []

        tampered = []
        try:
            # List processes with PID, Comm, and CPU %
            out = subprocess.check_output(
                ["ps", "-eo", "pid,comm,%cpu,nice", "--sort=-%cpu", "--no-headers"],
                universal_newlines=True
            )
            for line in out.strip().split("\n"):
                if not line.strip():
                    continue
                parts = line.split()
                if len(parts) < 4:
                    continue
                pid_str, comm, cpu_str, nice_str = parts[0], parts[1], parts[2], parts[3]
                try:
                    pid = int(pid_str)
                    cpu = float(cpu_str)
                    nice = int(nice_str)
                except ValueError:
                    continue

                if pid in (0, 1, os.getpid()):
                    continue

                # If CPU consumption exceeds threshold
                if cpu >= self.cpu_hog_threshold:
                    comm_lower = comm.lower()
                    if comm_lower in self.protected_processes or any(p in comm_lower for p in self.protected_processes):
                        continue

                    # Renice process if currently running with normal priority (nice <= 0)
                    if nice < 10:
                        try:
                            subprocess.run(["renice", "+10", "-p", str(pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                            subprocess.run(["ionice", "-c", "3", "-p", str(pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                            tampered.append(f"{comm} (PID {pid}, CPU {cpu}%) -> reniced +10 & ionice idle")
                        except Exception:
                            pass
        except Exception as e:
            self.logger.error(f"Error taming CPU hogs: {e}")

        return tampered

    def write_state(self, ram_pct: float, cpu_pct: float, status_msg: str):
        """Writes current status into /run/autoboost.state for instant CLI inspection."""
        try:
            with open(STATE_FILE, "w") as f:
                f.write(f"TIMESTAMP={int(time.time())}\n")
                f.write(f"RAM_PCT={ram_pct}\n")
                f.write(f"CPU_PCT={cpu_pct}\n")
                f.write(f"STATUS={status_msg}\n")
                f.write(f"LAST_BOOST={int(self.last_boost_time)}\n")
        except Exception:
            pass

    def run_boost(self, reason: str = "Threshold reached") -> Dict:
        """Executes full optimization and logs details."""
        ram_before, total_mb, avail_before, buff_before = self.get_memory_usage()
        cpu_before = self.get_cpu_usage()

        self.logger.info(f"⚡ [AUTOBOOST TRIGGERED] Reason: {reason} | RAM: {ram_before}% ({avail_before}MB free), CPU: {cpu_before}%")

        mem_actions = self.boost_memory()
        tamed_procs = self.tame_cpu_hogs()

        time.sleep(0.5)
        ram_after, _, avail_after, buff_after = self.get_memory_usage()
        freed_mb = max(0, avail_after - avail_before)

        summary = (
            f"✅ Boost Complete | Freed ~{freed_mb}MB RAM | "
            f"Avail RAM: {avail_before}MB -> {avail_after}MB ({ram_before}% -> {ram_after}%) | "
            f"Tamed {len(tamed_procs)} processes"
        )
        self.logger.info(summary)
        if tamed_procs:
            self.logger.info("   Tamed processes: " + "; ".join(tamed_procs))

        self.last_boost_time = time.time()
        self.write_state(ram_after, cpu_before, summary)

        return {
            "ram_before": ram_before,
            "ram_after": ram_after,
            "avail_before_mb": avail_before,
            "avail_after_mb": avail_after,
            "freed_mb": freed_mb,
            "actions": mem_actions,
            "tamed_procs": tamed_procs
        }

    def start(self):
        """Main monitoring loop."""
        self.logger.info("🚀 AutoBoost Daemon started (Monitoring RAM & CPU)")
        
        # Initialize CPU baseline
        self.get_cpu_usage()

        while self.running:
            try:
                time.sleep(self.interval)

                ram_usage, total_mb, avail_mb, buff_mb = self.get_memory_usage()
                cpu_usage = self.get_cpu_usage()

                ram_triggered = (ram_usage >= self.ram_threshold)
                cpu_triggered = (cpu_usage >= self.cpu_threshold)

                now = time.time()
                is_cooldown_active = (now - self.last_boost_time) < self.cooldown

                if (ram_triggered or cpu_triggered) and not is_cooldown_active:
                    reasons = []
                    if ram_triggered:
                        reasons.append(f"High RAM ({ram_usage}% >= {self.ram_threshold}%)")
                    if cpu_triggered:
                        reasons.append(f"High CPU ({cpu_usage}% >= {self.cpu_threshold}%)")
                    self.run_boost(", ".join(reasons))
                else:
                    status = "Normal" if not is_cooldown_active else "Cooldown active"
                    self.write_state(ram_usage, cpu_usage, status)

            except Exception as e:
                self.logger.error(f"Unexpected loop error: {e}", exc_info=True)

    def stop(self):
        self.logger.info("🛑 AutoBoost Daemon stopping")
        self.running = False

def handle_signal(sig, frame):
    daemon.stop()
    sys.exit(0)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--once":
        # One-shot manual boost execution
        d = AutoBoostDaemon()
        result = d.run_boost(reason="Manual boost via CLI")
        print(f"Freed: {result['freed_mb']} MB (Avail: {result['avail_before_mb']} MB -> {result['avail_after_mb']} MB)")
        sys.exit(0)

    daemon = AutoBoostDaemon()
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    daemon.start()
