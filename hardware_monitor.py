from __future__ import annotations

import gc
import os
import platform
import shutil
import socket
import statistics
import subprocess
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Deque, Dict, List, Optional, Tuple

import psutil

_GB = 1024 ** 3
_MB = 1024 ** 2
_NO_WINDOW = 0x08000000 if platform.system() == "Windows" else 0


@dataclass
class TelemetrySnapshot:
    cpu: float = 0.0
    ram: float = 0.0
    gpu: float = 0.0
    per_core: List[float] = field(default_factory=list)
    cpu_freq_mhz: float = 0.0
    cpu_temp: Optional[float] = None
    gpu_temp: Optional[float] = None
    gpu_fan: Optional[float] = None
    fan_rpm: Optional[float] = None
    gpu_name: str = ""
    gpu_mem_used_mb: Optional[float] = None
    gpu_mem_total_mb: Optional[float] = None
    battery_percent: Optional[float] = None
    battery_plugged: bool = True
    battery_secs: Optional[int] = None
    disk_used_percent: float = 0.0
    disk_read_mb_s: float = 0.0
    disk_write_mb_s: float = 0.0
    disks: List[Tuple[str, float, float, float]] = field(default_factory=list)
    net_up_kb_s: float = 0.0
    net_down_kb_s: float = 0.0
    net_total_sent_gb: float = 0.0
    net_total_recv_gb: float = 0.0
    net_ifaces: List[Tuple[str, str]] = field(default_factory=list)
    wifi: dict = field(default_factory=dict)
    bluetooth: dict = field(default_factory=dict)
    ram_total_gb: float = 0.0
    used_ram_gb: float = 0.0
    ram_available_gb: float = 0.0
    swap_percent: float = 0.0
    swap_used_gb: float = 0.0
    swap_total_gb: float = 0.0
    process_count: int = 0
    thread_count: int = 0
    uptime_text: str = "00:00:00"
    disk_used_gb: float = 0.0
    disk_total_gb: float = 0.0
    host: str = ""
    platform_name: str = ""
    top_procs: List[Tuple[str, float]] = field(default_factory=list)
    apps: List[Tuple[str, float, int]] = field(default_factory=list)  # name, total MB, instances


@dataclass
class TelemetrySeries:
    cpu: Deque[float] = field(default_factory=lambda: deque(maxlen=120))
    ram: Deque[float] = field(default_factory=lambda: deque(maxlen=120))
    gpu: Deque[float] = field(default_factory=lambda: deque(maxlen=120))
    net: Deque[float] = field(default_factory=lambda: deque(maxlen=120))


class HardwareMonitor:
    """Two background threads:

    * fast loop  -> CPU/RAM/swap/IO/battery every ``interval`` (never blocks)
    * slow loop  -> GPU, process scan, disks, temps, WiFi/Bluetooth (may block)

    The fast loop assembles each snapshot from its own cheap reads plus the
    latest cached slow values, so the UI stays continuous.
    """

    def __init__(self, interval: float = 0.5):
        self.interval = interval
        self.series = TelemetrySeries()
        self.latest = TelemetrySnapshot(host=platform.node(),
                                        platform_name=f"{platform.system()} {platform.release()}")
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._threads: List[threading.Thread] = []

        self._last_disk = psutil.disk_io_counters()
        self._last_net = psutil.net_io_counters()
        self._last_t = time.time()

        # cached slow values
        self._gpu = 0.0
        self._gpu_temp = self._gpu_fan = self._gpu_mem_used = self._gpu_mem_total = None
        self._gpu_name = ""
        self._cpu_temp: Optional[float] = None
        self._cpu_temp_supported: Optional[bool] = None
        self._fan_rpm: Optional[float] = None
        self._lhm_ok: Optional[bool] = None
        self._thread_count = 0
        self._top_procs: List[Tuple[str, float]] = []
        self._apps: List[Tuple[str, float, int]] = []
        self._disks: List[Tuple[str, float, float, float]] = []
        self._net_ifaces: List[Tuple[str, str]] = []
        self._wifi: dict = {}
        self._bt: dict = {}

        self._nvidia = shutil.which("nvidia-smi")
        self.static = self._gather_static()
        psutil.cpu_percent(interval=None, percpu=True)

    # ---- static specs ----------------------------------------------------
    def _gather_static(self) -> dict:
        try:
            freq = psutil.cpu_freq()
        except Exception:
            freq = None
        return {
            "cpu_model": self._cpu_model(),
            "cores": psutil.cpu_count(logical=False) or 0,
            "threads": psutil.cpu_count(logical=True) or 0,
            "cpu_freq_max": round(freq.max) if freq and freq.max else 0,
            "ram_total_gb": round(psutil.virtual_memory().total / _GB, 1),
            "host": platform.node(),
            "os": f"{platform.system()} {platform.release()} (build {platform.version().split('.')[-1]})",
            "python": platform.python_version(),
            "ip": self._ip(),
            "boot_time": datetime.fromtimestamp(psutil.boot_time()).strftime("%Y-%m-%d %H:%M:%S"),
        }

    @staticmethod
    def _cpu_model() -> str:
        try:
            if platform.system() == "Windows":
                import winreg
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                     r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
                val, _ = winreg.QueryValueEx(key, "ProcessorNameString")
                winreg.CloseKey(key)
                return val.strip()
        except Exception:
            pass
        return platform.processor() or "Unknown CPU"

    @staticmethod
    def _ip() -> str:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            try:
                return socket.gethostbyname(socket.gethostname())
            except Exception:
                return "N/A"

    # ---- lifecycle -------------------------------------------------------
    def start(self) -> None:
        if self._threads:
            return
        self._stop.clear()
        self._threads = [
            threading.Thread(target=self._fast_loop, daemon=True),
            threading.Thread(target=self._slow_loop, daemon=True),
        ]
        for t in self._threads:
            t.start()

    def stop(self) -> None:
        self._stop.set()
        for t in self._threads:
            t.join(timeout=1.0)
        self._threads = []

    # ---- fast loop (cheap, never blocks) ---------------------------------
    def _fast_loop(self) -> None:
        while not self._stop.is_set():
            try:
                self._sample_fast()
            except Exception:
                pass
            self._stop.wait(self.interval)

    def _sample_fast(self) -> None:
        now = time.time()
        elapsed = max(0.001, now - self._last_t)

        per_core = psutil.cpu_percent(interval=None, percpu=True)
        cpu = statistics.fmean(per_core) if per_core else psutil.cpu_percent(interval=None)
        try:
            f = psutil.cpu_freq()
            cpu_freq = f.current if f else 0.0
        except Exception:
            cpu_freq = 0.0
        vm = psutil.virtual_memory()
        sm = psutil.swap_memory()
        disk = psutil.disk_usage(os.path.abspath(os.sep))

        disk_io = psutil.disk_io_counters()
        net_io = psutil.net_io_counters()
        read_mb_s = write_mb_s = up_kb_s = down_kb_s = 0.0
        if self._last_disk and disk_io:
            read_mb_s = max(0.0, (disk_io.read_bytes - self._last_disk.read_bytes) / _MB / elapsed)
            write_mb_s = max(0.0, (disk_io.write_bytes - self._last_disk.write_bytes) / _MB / elapsed)
        if self._last_net and net_io:
            up_kb_s = max(0.0, (net_io.bytes_sent - self._last_net.bytes_sent) / 1024 / elapsed)
            down_kb_s = max(0.0, (net_io.bytes_recv - self._last_net.bytes_recv) / 1024 / elapsed)
        self._last_disk, self._last_net, self._last_t = disk_io, net_io, now

        batt = psutil.sensors_battery()
        if batt is not None:
            bp, bpl = float(batt.percent), bool(batt.power_plugged)
            bs = None if batt.secsleft in (psutil.POWER_TIME_UNLIMITED, psutil.POWER_TIME_UNKNOWN) else int(batt.secsleft)
        else:
            bp, bpl, bs = None, True, None

        uptime = str(timedelta(seconds=int(time.time() - psutil.boot_time())))

        snap = TelemetrySnapshot(
            cpu=cpu, ram=vm.percent, gpu=self._gpu, per_core=per_core, cpu_freq_mhz=cpu_freq,
            cpu_temp=self._cpu_temp, gpu_temp=self._gpu_temp, gpu_fan=self._gpu_fan, fan_rpm=self._fan_rpm,
            gpu_name=self._gpu_name, gpu_mem_used_mb=self._gpu_mem_used, gpu_mem_total_mb=self._gpu_mem_total,
            battery_percent=bp, battery_plugged=bpl, battery_secs=bs,
            disk_used_percent=disk.percent, disk_read_mb_s=read_mb_s, disk_write_mb_s=write_mb_s,
            disks=self._disks, net_up_kb_s=up_kb_s, net_down_kb_s=down_kb_s,
            net_total_sent_gb=(net_io.bytes_sent / _GB) if net_io else 0.0,
            net_total_recv_gb=(net_io.bytes_recv / _GB) if net_io else 0.0,
            net_ifaces=self._net_ifaces, wifi=self._wifi, bluetooth=self._bt,
            ram_total_gb=vm.total / _GB, used_ram_gb=vm.used / _GB, ram_available_gb=vm.available / _GB,
            swap_percent=sm.percent, swap_used_gb=sm.used / _GB, swap_total_gb=sm.total / _GB,
            process_count=len(psutil.pids()), thread_count=self._thread_count, uptime_text=uptime,
            disk_used_gb=disk.used / _GB, disk_total_gb=disk.total / _GB,
            host=self.latest.host, platform_name=self.latest.platform_name,
            top_procs=self._top_procs, apps=self._apps,
        )
        with self._lock:
            self.latest = snap
            self.series.cpu.append(cpu)
            self.series.ram.append(vm.percent)
            self.series.gpu.append(self._gpu)
            self.series.net.append(min(100.0, (up_kb_s + down_kb_s) / 256.0))

    # ---- slow loop (heavy probes, off the fast path) ---------------------
    def _slow_loop(self) -> None:
        last = {"gpu": 0.0, "proc": 0.0, "disk": 0.0, "temp": 0.0, "net": 0.0}
        while not self._stop.is_set():
            now = time.time()
            try:
                if now - last["gpu"] >= 2.0:
                    last["gpu"] = now; self._probe_gpu()
                if now - last["proc"] >= 2.0:
                    last["proc"] = now; self._probe_procs()
                if now - last["disk"] >= 4.0:
                    last["disk"] = now; self._probe_disks()
                if now - last["temp"] >= 4.0:
                    last["temp"] = now; self._probe_cpu_temp()
                if now - last["net"] >= 6.0:
                    last["net"] = now; self._probe_connectivity()
            except Exception:
                pass
            self._stop.wait(0.5)

    def _probe_gpu(self) -> None:
        if not self._nvidia:
            return
        try:
            out = subprocess.check_output(
                [self._nvidia,
                 "--query-gpu=utilization.gpu,temperature.gpu,fan.speed,memory.used,memory.total,name",
                 "--format=csv,noheader,nounits"],
                stderr=subprocess.DEVNULL, timeout=1.5, text=True, creationflags=_NO_WINDOW,
            ).strip().splitlines()
            if out:
                p = [x.strip() for x in out[0].split(",")]
                self._gpu = self._f(p[0], 0.0) or 0.0
                self._gpu_temp = self._f(p[1], None) if len(p) > 1 else None
                self._gpu_fan = self._f(p[2], None) if len(p) > 2 else None
                self._gpu_mem_used = self._f(p[3], None) if len(p) > 3 else None
                self._gpu_mem_total = self._f(p[4], None) if len(p) > 4 else None
                self._gpu_name = ",".join(p[5:]).strip() if len(p) > 5 else ""
        except Exception:
            pass

    def _probe_procs(self) -> None:
        threads = 0
        agg: Dict[str, List[float]] = {}
        for p in psutil.process_iter(attrs=["name", "memory_info", "num_threads"]):
            try:
                info = p.info
                threads += info.get("num_threads") or 0
                mi = info.get("memory_info")
                if mi is None:
                    continue
                name = info.get("name") or "?"
                mb = mi.rss / _MB
                if name in agg:
                    agg[name][0] += mb
                    agg[name][1] += 1
                else:
                    agg[name] = [mb, 1]
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        apps = sorted(((n, v[0], int(v[1])) for n, v in agg.items()), key=lambda x: x[1], reverse=True)
        self._thread_count = threads
        self._apps = apps[:40]
        self._top_procs = [(n, mb) for n, mb, _ in apps[:5]]

    def _probe_disks(self) -> None:
        disks = []
        for part in psutil.disk_partitions(all=False):
            try:
                u = psutil.disk_usage(part.mountpoint)
                disks.append((part.device.rstrip("\\"), u.percent, u.used / _GB, u.total / _GB))
            except Exception:
                continue
        self._disks = disks

    def _probe_cpu_temp(self) -> None:
        # 1) LibreHardwareMonitor (best on Windows laptops: real CPU temp + fan RPM)
        if self._lhm_ok is not False and platform.system() == "Windows":
            ct, fan = self._probe_lhm()
            if ct is not None or fan is not None:
                self._lhm_ok = True
                if ct is not None:
                    self._cpu_temp = ct
                if fan is not None:
                    self._fan_rpm = fan
                return
            self._lhm_ok = False  # not running; stop trying until app restart

        if self._cpu_temp_supported is False:
            return
        # 2) psutil (real on Linux, usually empty on Windows)
        try:
            temps = psutil.sensors_temperatures()
            for key in ("coretemp", "k10temp", "acpitz"):
                if temps.get(key):
                    self._cpu_temp = float(temps[key][0].current)
                    self._cpu_temp_supported = True
                    return
        except Exception:
            pass
        # 3) ACPI thermal zone (often access-denied without admin)
        if platform.system() == "Windows":
            try:
                out = subprocess.check_output(
                    ["powershell", "-NoProfile", "-Command",
                     "(Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature "
                     "-ErrorAction Stop | Select-Object -First 1 -ExpandProperty CurrentTemperature)"],
                    stderr=subprocess.DEVNULL, timeout=3.0, text=True, creationflags=_NO_WINDOW,
                ).strip()
                val = self._f(out, None)
                if val and val > 2000:
                    self._cpu_temp = round(val / 10.0 - 273.15, 1)
                    self._cpu_temp_supported = True
                    return
            except Exception:
                pass
        self._cpu_temp_supported = False

    def _probe_lhm(self):
        """Read CPU temp + fan RPM from LibreHardwareMonitor's web server (JSON on
        :8085) or, failing that, the OHM/LHM WMI namespace. Returns (cpu_temp, fan_rpm)."""
        ct, fan = self._probe_lhm_http()
        if ct is not None or fan is not None:
            return ct, fan
        for ns in ("root/LibreHardwareMonitor", "root/OpenHardwareMonitor"):
            try:
                out = subprocess.check_output(
                    ["powershell", "-NoProfile", "-Command",
                     f"Get-CimInstance -Namespace {ns} -ClassName Sensor -ErrorAction Stop | "
                     "Where-Object { $_.SensorType -in 'Temperature','Fan' } | "
                     "ForEach-Object { \"$($_.SensorType)|$($_.Name)|$($_.Value)\" }"],
                    stderr=subprocess.DEVNULL, timeout=2.5, text=True, creationflags=_NO_WINDOW,
                )
                temps, fans = [], []
                for line in out.splitlines():
                    parts = line.split("|")
                    if len(parts) != 3:
                        continue
                    stype, name, val = parts
                    v = self._f(val, None)
                    if v is None:
                        continue
                    if stype == "Temperature" and any(k in name for k in ("CPU", "Core", "Package")):
                        temps.append(v)
                    elif stype == "Fan" and v > 0:
                        fans.append(v)
                if temps or fans:
                    return (max(temps) if temps else None), (max(fans) if fans else None)
            except Exception:
                continue
        return None, None

    def _probe_lhm_http(self):
        """Parse LibreHardwareMonitor's web-server JSON (Options -> Remote Web Server)."""
        try:
            import json
            import urllib.request
            with urllib.request.urlopen("http://localhost:8085/data.json", timeout=1.5) as r:
                data = json.loads(r.read().decode("utf-8", "ignore"))
        except Exception:
            return None, None
        temps, fans = [], []

        def walk(node):
            txt = node.get("Text", "") or ""
            val = (node.get("Value", "") or "").strip()
            num = self._lead_float(val)
            if num is not None:
                if val.upper().endswith("RPM"):
                    if num > 0:
                        fans.append(num)
                elif val.endswith("C") and any(k in txt for k in ("CPU", "Core", "Package")):
                    temps.append(num)
            for child in node.get("Children", []) or []:
                walk(child)

        walk(data)
        return (max(temps) if temps else None), (max(fans) if fans else None)

    @staticmethod
    def _lead_float(s):
        try:
            return float(str(s).split()[0].replace(",", "."))
        except (ValueError, IndexError, AttributeError):
            return None

    def _probe_connectivity(self) -> None:
        # network interfaces (cheap)
        try:
            stats = psutil.net_if_stats()
            addrs = psutil.net_if_addrs()
            ifaces = []
            for name, st in stats.items():
                if not st.isup:
                    continue
                ip = ""
                for a in addrs.get(name, []):
                    if a.family == socket.AF_INET:
                        ip = a.address
                        break
                ifaces.append((name, ip or "-"))
            self._net_ifaces = ifaces
        except Exception:
            pass

        if platform.system() != "Windows":
            return
        # WiFi via netsh
        try:
            out = subprocess.check_output(["netsh", "wlan", "show", "interfaces"],
                                          stderr=subprocess.DEVNULL, timeout=3.0, text=True,
                                          creationflags=_NO_WINDOW)
            wifi = {"state": "disconnected", "ssid": "-", "signal": 0}
            for line in out.splitlines():
                if ":" not in line:
                    continue
                k, v = (x.strip() for x in line.split(":", 1))
                kl = k.lower()
                if kl == "state":
                    wifi["state"] = v.lower()
                elif kl == "ssid" and "bssid" not in kl:
                    wifi["ssid"] = v or "-"
                elif kl == "signal":
                    wifi["signal"] = self._f(v.replace("%", ""), 0) or 0
            self._wifi = wifi
        except Exception:
            self._wifi = {"state": "n/a", "ssid": "-", "signal": 0}
        # Bluetooth via PnP
        try:
            out = subprocess.check_output(
                ["powershell", "-NoProfile", "-Command",
                 "Get-PnpDevice -Class Bluetooth -PresentOnly -Status OK | "
                 "Select-Object -ExpandProperty FriendlyName"],
                stderr=subprocess.DEVNULL, timeout=3.0, text=True, creationflags=_NO_WINDOW)
            names = [l.strip() for l in out.splitlines() if l.strip()]
            self._bt = {"present": bool(names), "devices": names[:12]}
        except Exception:
            self._bt = {"present": False, "devices": []}

    @staticmethod
    def _f(value, default):
        try:
            return float(str(value).strip())
        except (ValueError, TypeError):
            return default

    # ---- consumers -------------------------------------------------------
    def read(self) -> Tuple[TelemetrySnapshot, Dict[str, list]]:
        with self._lock:
            s = self.latest
            history = {k: list(getattr(self.series, k)) for k in ("cpu", "ram", "gpu", "net")}
        return s, history

    # ---- pit-control actions --------------------------------------------
    def optimize_system(self) -> None:
        gc.collect()

    def cleanup_memory(self) -> None:
        gc.collect()
        try:
            import ctypes
            ctypes.windll.psapi.EmptyWorkingSet(-1)
        except Exception:
            pass

    def cooling_mode(self) -> None:
        try:
            p = psutil.Process(os.getpid())
            p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS if platform.system() == "Windows" else 10)
        except Exception:
            pass
