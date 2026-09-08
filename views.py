from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk

from benchmark import run_benchmark, tier
from gauges import CoreBars, NeonCard, ProcessMonitor, TachometerGauge, VerticalGauge
from telemetry import TelemetryGraph
from theme import RaceTheme, set_animations_paused


def _kv(parent, key, value, family, big=False):
    row = tk.Frame(parent, bg=RaceTheme.PANEL)
    row.pack(fill="x", padx=12, pady=2)
    tk.Label(row, text=key, bg=RaceTheme.PANEL, fg=RaceTheme.TEXT_DIM, font=(family, 8)).pack(anchor="w")
    lbl = tk.Label(row, text=value, bg=RaceTheme.PANEL, fg=RaceTheme.TEXT,
                   font=(family, 14 if big else 11, "bold"))
    lbl.pack(anchor="w")
    return lbl


def _temp(v):
    return f"{v:.0f}°C" if v is not None else "N/A"


class BaseView(ttk.Frame):
    def __init__(self, parent, family):
        super().__init__(parent, style="Race.TFrame")
        self.family = family

    def refresh(self, snap, history, static):  # overridden
        pass


# ---------------------------------------------------------------------------
class DashboardView(BaseView):
    def __init__(self, parent, family):
        super().__init__(parent, family)
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=2)
        self.columnconfigure(2, weight=1)
        self.rowconfigure(0, weight=3)
        self.rowconfigure(1, weight=2)
        self.rowconfigure(2, weight=0)

        self.fuel = VerticalGauge(self, title="FUEL TANK", subtitle="RAM")
        self.fuel.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        self.tach = TachometerGauge(self, title="ENGINE  (CPU)")
        self.tach.grid(row=0, column=1, sticky="nsew", padx=8, pady=8)
        self.turbo = VerticalGauge(self, title="TURBO BOOST", subtitle="GPU")
        self.turbo.grid(row=0, column=2, sticky="nsew", padx=8, pady=8)

        traces = ttk.Frame(self, style="Race.TFrame")
        traces.grid(row=1, column=0, columnspan=3, sticky="nsew")
        for c in range(4):
            traces.columnconfigure(c, weight=1)
        traces.rowconfigure(0, weight=1)
        self.g_cpu = TelemetryGraph(traces, "CPU TRACE", RaceTheme.OPTIMAL)
        self.g_ram = TelemetryGraph(traces, "RAM TRACE", RaceTheme.CAUTION)
        self.g_gpu = TelemetryGraph(traces, "GPU TRACE", RaceTheme.SIGNAL)
        self.g_net = TelemetryGraph(traces, "NET TRACE", RaceTheme.NEON)
        for i, g in enumerate((self.g_cpu, self.g_ram, self.g_gpu, self.g_net)):
            g.grid(row=0, column=i, sticky="nsew", padx=8, pady=8)

        strip = tk.Frame(self, bg=RaceTheme.BG)
        strip.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(4, 0))
        self.stat = tk.Label(strip, text="", bg=RaceTheme.BG, fg=RaceTheme.TEXT_DIM, font=(family, 10))
        self.stat.pack(anchor="w", padx=10, pady=6)

    def refresh(self, snap, history, static):
        self.tach.set_value(snap.cpu)
        self.fuel.set_value(snap.ram)
        self.turbo.set_value(snap.gpu)
        self.g_cpu.set_values(history["cpu"])
        self.g_ram.set_values(history["ram"])
        self.g_gpu.set_values(history["gpu"])
        self.g_net.set_values(history["net"])
        batt = f"{snap.battery_percent:.0f}% {'AC' if snap.battery_plugged else 'BATT'}" if snap.battery_percent is not None else "N/A"
        self.stat.configure(text=(f"Uptime {snap.uptime_text}    •    "
                                  f"RAM {snap.used_ram_gb:.1f}/{snap.ram_total_gb:.1f} GB    •    "
                                  f"Disk C: {snap.disk_used_percent:.0f}%    •    "
                                  f"Processes {snap.process_count}    •    Battery {batt}"))


# ---------------------------------------------------------------------------
class PerformanceView(BaseView):
    def __init__(self, parent, family):
        super().__init__(parent, family)
        self.columnconfigure(0, weight=2)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=2)
        self.rowconfigure(1, weight=3)

        metrics = NeonCard(self, "LIVE METRICS")
        metrics.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        self.m_cpu = _kv(metrics, "CPU", "0%", family, big=True)
        self.m_clock = _kv(metrics, "CPU Clock", "0 GHz", family)
        self.m_ram = _kv(metrics, "RAM", "0%", family, big=True)
        self.m_gpu = _kv(metrics, "GPU", "0%", family, big=True)
        self.m_temps = _kv(metrics, "Temps (CPU / GPU)", "N/A", family)
        self.m_fan = _kv(metrics, "Fan", "N/A", family)
        self.m_swap = _kv(metrics, "Swap", "0%", family)

        proc_card = NeonCard(self, "TOP CONSUMERS")
        proc_card.grid(row=0, column=1, sticky="nsew", padx=8, pady=8)
        self.proc = ProcessMonitor(proc_card)
        self.proc.pack(fill="both", expand=True, padx=8, pady=8)

        core_card = NeonCard(self, "PER-CORE LOAD")
        core_card.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=8, pady=8)
        self.cores = CoreBars(core_card)
        self.cores.pack(fill="both", expand=True, padx=8, pady=8)

    def refresh(self, snap, history, static):
        self.m_cpu.configure(text=f"{snap.cpu:.1f}%", fg=RaceTheme.usage_color(snap.cpu))
        self.m_clock.configure(text=f"{snap.cpu_freq_mhz/1000:.2f} GHz  (max {static['cpu_freq_max']/1000:.1f})" if snap.cpu_freq_mhz else "N/A")
        self.m_ram.configure(text=f"{snap.ram:.1f}%  ({snap.used_ram_gb:.1f}/{snap.ram_total_gb:.1f} GB)", fg=RaceTheme.usage_color(snap.ram))
        self.m_gpu.configure(text=f"{snap.gpu:.0f}%" + (f"  {snap.gpu_mem_used_mb:.0f}/{snap.gpu_mem_total_mb:.0f} MB" if snap.gpu_mem_total_mb else ""), fg=RaceTheme.usage_color(snap.gpu))
        self.m_temps.configure(text=f"{_temp(snap.cpu_temp)}  /  {_temp(snap.gpu_temp)}")
        if snap.fan_rpm:
            fan_txt = f"{snap.fan_rpm:.0f} RPM"
        elif snap.gpu_fan is not None:
            fan_txt = f"GPU {snap.gpu_fan:.0f}%"
        else:
            fan_txt = "N/A (install LibreHardwareMonitor)"
        self.m_fan.configure(text=fan_txt)
        self.m_swap.configure(text=f"{snap.swap_percent:.0f}%  ({snap.swap_used_gb:.1f}/{snap.swap_total_gb:.1f} GB)")
        self.proc.set_procs(snap.top_procs)
        self.cores.set_values(snap.per_core)


# ---------------------------------------------------------------------------
class ConnectivityView(BaseView):
    def __init__(self, parent, family):
        super().__init__(parent, family)
        for c in range(3):
            self.columnconfigure(c, weight=1)
        self.rowconfigure(0, weight=1)

        wifi = NeonCard(self, "WI-FI")
        wifi.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        self.w_state = _kv(wifi, "Status", "-", family, big=True)
        self.w_ssid = _kv(wifi, "Network (SSID)", "-", family)
        self.w_signal = _kv(wifi, "Signal", "-", family)
        self.sig = tk.Canvas(wifi, height=16, bg=RaceTheme.PANEL, highlightthickness=0)
        self.sig.pack(fill="x", padx=12, pady=(2, 10))

        bt = NeonCard(self, "BLUETOOTH")
        bt.grid(row=0, column=1, sticky="nsew", padx=8, pady=8)
        self.b_state = _kv(bt, "Adapter", "-", family, big=True)
        self.b_list = tk.Label(bt, text="", bg=RaceTheme.PANEL, fg=RaceTheme.TEXT, font=(family, 9),
                               justify="left", anchor="nw")
        self.b_list.pack(fill="both", expand=True, padx=12, pady=(2, 10))

        net = NeonCard(self, "NETWORK")
        net.grid(row=0, column=2, sticky="nsew", padx=8, pady=8)
        self.n_ip = _kv(net, "IP Address", "-", family, big=True)
        self.n_speed = _kv(net, "Throughput", "up 0 | dn 0 KB/s", family)
        self.n_total = _kv(net, "Session Total", "-", family)
        self.n_if = tk.Label(net, text="", bg=RaceTheme.PANEL, fg=RaceTheme.TEXT_DIM, font=(family, 9),
                             justify="left", anchor="nw")
        self.n_if.pack(fill="both", expand=True, padx=12, pady=(2, 10))

    def refresh(self, snap, history, static):
        w = snap.wifi or {}
        state = str(w.get("state", "n/a")).title()
        connected = "connect" in state.lower()
        self.w_state.configure(text=state, fg=RaceTheme.OPTIMAL if connected else RaceTheme.TEXT_DIM)
        self.w_ssid.configure(text=str(w.get("ssid", "-")))
        sig = int(w.get("signal", 0) or 0)
        self.w_signal.configure(text=f"{sig}%")
        self.sig.delete("all")
        cw = self.sig.winfo_width() or 200
        self.sig.create_rectangle(2, 3, cw - 2, 13, outline="#1f2a38")
        self.sig.create_rectangle(2, 3, 2 + (cw - 4) * sig / 100, 13,
                                  fill=RaceTheme.usage_color(100 - sig), outline="")

        b = snap.bluetooth or {}
        present = b.get("present")
        self.b_state.configure(text="ON / Present" if present else "Off / None",
                               fg=RaceTheme.OPTIMAL if present else RaceTheme.TEXT_DIM)
        devs = b.get("devices", [])
        self.b_list.configure(text="\n".join(f"• {d}" for d in devs) if devs else "No devices detected")

        self.n_ip.configure(text=static.get("ip", "-"))
        self.n_speed.configure(text=f"up {snap.net_up_kb_s:.0f} | dn {snap.net_down_kb_s:.0f} KB/s")
        self.n_total.configure(text=f"up {snap.net_total_sent_gb:.2f} GB | dn {snap.net_total_recv_gb:.2f} GB")
        self.n_if.configure(text="\n".join(f"{n}: {ip}" for n, ip in snap.net_ifaces) or "No active interfaces")


# ---------------------------------------------------------------------------
class _ScrollText(BaseView):
    def __init__(self, parent, family, title):
        super().__init__(parent, family)
        tk.Label(self, text=title, bg=RaceTheme.BG, fg=RaceTheme.TEXT,
                 font=(family, 13, "bold")).pack(anchor="w", padx=12, pady=(8, 4))
        wrap = tk.Frame(self, bg=RaceTheme.BG)
        wrap.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.text = tk.Text(wrap, bg=RaceTheme.PANEL, fg=RaceTheme.TEXT, relief="flat",
                            font=("Consolas", 10), wrap="none", padx=12, pady=10,
                            highlightthickness=0)
        sb = ttk.Scrollbar(wrap, command=self.text.yview)
        self.text.configure(yscrollcommand=sb.set, state="disabled")
        sb.pack(side="right", fill="y")
        self.text.pack(side="left", fill="both", expand=True)

    def _set_text(self, content):
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("end", content)
        self.text.configure(state="disabled")


class AppsView(_ScrollText):
    def __init__(self, parent, family):
        super().__init__(parent, family, "RUNNING APPLICATIONS  (grouped, by RAM)")

    def refresh(self, snap, history, static):
        lines = [f"{'APPLICATION':<30} {'COUNT':>6} {'RAM':>12}",
                 "-" * 50]
        for name, mb, count in snap.apps:
            lines.append(f"{name[:30]:<30} {('x' + str(count)):>6} {mb:>9,.0f} MB")
        lines.append("")
        lines.append(f"Total: {snap.process_count} processes / {snap.thread_count} threads")
        self._set_text("\n".join(lines))


class SystemView(_ScrollText):
    def __init__(self, parent, family):
        super().__init__(parent, family, "FULL SYSTEM STATUS")

    def refresh(self, snap, history, static):
        self._set_text(render_system(snap, static))


def render_system(s, st) -> str:
    def hz(mhz):
        return f"{mhz/1000:.2f} GHz" if mhz else "N/A"

    L = []
    L += ["== IDENTITY ==",
          f"  Host     : {st['host']}",
          f"  OS       : {st['os']}",
          f"  Python   : {st['python']}",
          f"  Booted   : {st['boot_time']}",
          f"  Uptime   : {s.uptime_text}", ""]
    L += ["== CPU ==",
          f"  Model    : {st['cpu_model']}",
          f"  Cores    : {st['cores']} cores / {st['threads']} threads",
          f"  Clock    : {hz(s.cpu_freq_mhz)}  (max {hz(st['cpu_freq_max'])})",
          f"  Usage    : {s.cpu:.1f}%     Temp: {_temp(s.cpu_temp)}",
          f"  Fan      : {f'{s.fan_rpm:.0f} RPM' if s.fan_rpm else 'N/A'}"]
    if s.per_core:
        L.append("  Per-core : " + "  ".join(f"{i}:{v:>4.0f}%" for i, v in enumerate(s.per_core)))
    L += ["",
          "== MEMORY ==",
          f"  RAM      : {s.used_ram_gb:.1f} / {s.ram_total_gb:.1f} GB ({s.ram:.0f}%)  free {s.ram_available_gb:.1f} GB",
          f"  Swap     : {s.swap_used_gb:.1f} / {s.swap_total_gb:.1f} GB ({s.swap_percent:.0f}%)", "",
          "== GPU ==",
          f"  Name     : {s.gpu_name or 'N/A'}",
          f"  Usage    : {s.gpu:.0f}%   Temp {_temp(s.gpu_temp)}   Fan {f'{s.gpu_fan:.0f}%' if s.gpu_fan is not None else 'N/A'}"]
    if s.gpu_mem_total_mb:
        L.append(f"  VRAM     : {s.gpu_mem_used_mb:.0f} / {s.gpu_mem_total_mb:.0f} MB")
    L += ["", "== STORAGE =="]
    for dev, pct, used, total in s.disks:
        L.append(f"  {dev:<9}: {used:.0f} / {total:.0f} GB ({pct:.0f}%)")
    L += [f"  Activity : R {s.disk_read_mb_s:.1f}  W {s.disk_write_mb_s:.1f} MB/s", "",
          "== NETWORK ==",
          f"  IP       : {st['ip']}",
          f"  Session  : up {s.net_total_sent_gb:.2f} GB  down {s.net_total_recv_gb:.2f} GB",
          f"  Now      : up {s.net_up_kb_s:.0f}  down {s.net_down_kb_s:.0f} KB/s", "",
          "== BATTERY =="]
    if s.battery_percent is not None:
        state = "Charging / AC" if s.battery_plugged else "On battery"
        L.append(f"  Level    : {s.battery_percent:.0f}%  -  {state}")
    else:
        L.append("  Level    : N/A")
    return "\n".join(L)


# ---------------------------------------------------------------------------
class BenchmarkView(BaseView):
    def __init__(self, parent, family, cores, monitor=None):
        super().__init__(parent, family)
        self.cores = cores
        self.monitor = monitor
        self._lock = threading.Lock()
        self._state = {"stage": "Idle - press RUN", "pct": 0}
        self._results = None
        self._running = False

        tk.Label(self, text="BENCHMARK", bg=RaceTheme.BG, fg=RaceTheme.TEXT,
                 font=(family, 14, "bold")).pack(anchor="w", padx=14, pady=(8, 2))
        tk.Label(self, text=f"Stress-tests all {cores} threads, memory and disk, then scores it. Takes ~10s.",
                 bg=RaceTheme.BG, fg=RaceTheme.TEXT_DIM, font=(family, 9)).pack(anchor="w", padx=14, pady=(0, 10))

        self.btn = ttk.Button(self, text="RUN BENCHMARK", style="Pit.TButton", command=self.start)
        self.btn.pack(anchor="w", padx=14)

        ttk.Style(self).configure("Bench.Horizontal.TProgressbar", troughcolor=RaceTheme.PANEL,
                                  background=RaceTheme.SIGNAL, bordercolor=RaceTheme.PANEL)
        self.bar = ttk.Progressbar(self, mode="determinate", maximum=100,
                                   style="Bench.Horizontal.TProgressbar")
        self.bar.pack(fill="x", padx=14, pady=(12, 4))
        self.stage_lbl = tk.Label(self, text=self._state["stage"], bg=RaceTheme.BG,
                                  fg=RaceTheme.SIGNAL, font=(family, 10, "bold"))
        self.stage_lbl.pack(anchor="w", padx=14)

        card = NeonCard(self, "RESULTS")
        card.pack(fill="both", expand=True, padx=14, pady=12)
        self.out = tk.Text(card, bg=RaceTheme.PANEL, fg=RaceTheme.TEXT, relief="flat",
                           font=("Consolas", 11), wrap="none", padx=12, pady=10, highlightthickness=0)
        self.out.pack(fill="both", expand=True, padx=8, pady=8)
        self._set_out("No results yet.")

    def start(self):
        if self._running:
            return
        self._running = True
        self._results = None
        self.btn.configure(state="disabled")
        self._set_out("Running... CPU will redline. UI + sensors paused for an accurate score.")
        set_animations_paused(True)          # quiet the GIL for a clean single-core number
        if self.monitor:
            try:
                self.monitor.stop()
            except Exception:
                pass
        threading.Thread(target=self._worker, daemon=True).start()
        self._poll()

    def _restore(self):
        set_animations_paused(False)
        if self.monitor:
            try:
                self.monitor.start()
            except Exception:
                pass

    def _worker(self):
        def prog(stage, pct):
            with self._lock:
                self._state = {"stage": stage, "pct": pct}
        try:
            res = run_benchmark(prog, self.cores)
        except Exception as e:
            res = {"error": str(e)}
        with self._lock:
            self._results = res

    def _poll(self):
        if not self.winfo_exists():
            self._restore()
            return
        with self._lock:
            st = dict(self._state)
            res = self._results
        self.bar.configure(value=st["pct"])
        self.stage_lbl.configure(text=st["stage"])
        if res is not None:
            self._show(res)
            self._running = False
            self.btn.configure(state="normal")
            self._restore()
            return
        self.after(120, self._poll)

    def _show(self, r):
        if "error" in r:
            self._set_out("Benchmark error: " + r["error"])
            return
        lines = [
            f"  CPU single-core : {r['cpu_single']:>9,.0f} MB/s",
            f"  CPU all-cores   : {r['cpu_multi']:>9,.0f} MB/s   ({self.cores} threads)",
            f"  Parallel gain   : {r['parallel']:>9.1f}x",
            f"  Memory bandwidth: {r['mem_gbps']:>9.1f} GB/s",
            f"  Disk write/read : {r['disk_write']:>6,.0f} / {r['disk_read']:,.0f} MB/s",
            "  " + "-" * 42,
            f"  OVERALL SCORE   : {r['overall']:>9,}   [{tier(r['overall'])}]",
        ]
        self._set_out("\n".join(lines))

    def _set_out(self, content):
        self.out.configure(state="normal")
        self.out.delete("1.0", "end")
        self.out.insert("end", content)
        self.out.configure(state="disabled")

    def refresh(self, snap, history, static):
        pass
