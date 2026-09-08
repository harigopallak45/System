from __future__ import annotations

import threading
import time
import tkinter as tk
from tkinter import ttk

import appconfig
from hardware_monitor import HardwareMonitor
from theme import RaceTheme, apply_ttk_theme, set_accent
from views import (
    AppsView,
    BenchmarkView,
    ConnectivityView,
    DashboardView,
    PerformanceView,
    SystemView,
)
from windows import SettingsWindow

_DARK = "#0b0f14"


class MotorsportDashboard:
    MODES = [
        ("DASHBOARD", "DASHBOARD"),
        ("PERFORMANCE", "PERFORMANCE"),
        ("CONNECTIVITY", "WIFI / BT"),
        ("APPS", "APPS"),
        ("BENCHMARK", "BENCHMARK"),
        ("SYSTEM", "SYSTEM"),
    ]

    def __init__(self, root: tk.Tk):
        self.root = root
        self.config = appconfig.load()
        self._alerting = False
        self._auto_purge_last = 0.0
        self._refresh_ms = int(self.config.get("ui_refresh_ms", 200))
        set_accent(self.config.get("accent", "cyan"))

        root.title("Race Telemetry Console")
        root.configure(bg=RaceTheme.BG)
        root.geometry("1480x900")
        root.minsize(1100, 720)

        self.family = RaceTheme.font_family(root)
        self.style = ttk.Style(root)
        apply_ttk_theme(self.style, self.family)

        interval = max(0.1, float(self.config.get("monitor_interval", 500)) / 1000.0)
        self.monitor = HardwareMonitor(interval=interval)
        self.monitor.start()

        self._build()
        root.protocol("WM_DELETE_WINDOW", self._on_close)
        root.after(120, self._ui_tick)

    # ---- layout ----------------------------------------------------------
    def _build(self) -> None:
        outer = ttk.Frame(self.root, style="Race.TFrame")
        outer.pack(fill="both", expand=True, padx=10, pady=10)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(2, weight=1)

        # --- mode bar ---
        bar = tk.Frame(outer, bg=RaceTheme.BG)
        bar.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        modes = tk.Frame(bar, bg=RaceTheme.BG)
        modes.pack(side="left")
        self.mode_btns: dict[str, tk.Button] = {}
        for key, label in self.MODES:
            b = tk.Button(modes, text=label, command=lambda k=key: self._switch(k),
                          relief="flat", bd=0, padx=16, pady=9, cursor="hand2",
                          font=(self.family, 10, "bold"))
            b.pack(side="left", padx=3)
            self.mode_btns[key] = b

        actions = tk.Frame(bar, bg=RaceTheme.BG)
        actions.pack(side="right")
        for label, cmd in (("Nitro Purge", self._nitro_purge),
                           ("Cooling", self._cooling),
                           ("Settings", self._open_settings)):
            tk.Button(actions, text=label, command=cmd, relief="flat", bd=0, padx=14, pady=9,
                      cursor="hand2", font=(self.family, 10, "bold"),
                      bg=RaceTheme.PANEL, fg=RaceTheme.TEXT,
                      activebackground="#1b2735", activeforeground=RaceTheme.TEXT).pack(side="left", padx=3)

        # --- alert banner (row 1, shown on demand) ---
        self.banner = tk.Frame(outer, bg=RaceTheme.DANGER)
        self.banner_label = tk.Label(self.banner, text="", bg=RaceTheme.DANGER, fg=_DARK,
                                     font=(self.family, 12, "bold"))
        self.banner_label.pack(fill="x", padx=14, pady=6)

        # --- content (all views stacked in one cell) ---
        content = ttk.Frame(outer, style="Race.TFrame")
        content.grid(row=2, column=0, sticky="nsew")
        content.columnconfigure(0, weight=1)
        content.rowconfigure(0, weight=1)
        self.views = {
            "DASHBOARD": DashboardView(content, self.family),
            "PERFORMANCE": PerformanceView(content, self.family),
            "CONNECTIVITY": ConnectivityView(content, self.family),
            "APPS": AppsView(content, self.family),
            "BENCHMARK": BenchmarkView(content, self.family, self.monitor.static.get("threads", 4), self.monitor),
            "SYSTEM": SystemView(content, self.family),
        }
        for v in self.views.values():
            v.grid(row=0, column=0, sticky="nsew")

        # --- status bar ---
        self.pit_msg = tk.Label(outer, text="Pit systems nominal", bg=RaceTheme.BG,
                                fg=RaceTheme.TEXT_DIM, font=(self.family, 9))
        self.pit_msg.grid(row=3, column=0, sticky="w", pady=(6, 0))

        self.active = "DASHBOARD"
        self._switch("DASHBOARD")

    def _switch(self, key: str) -> None:
        self.active = key
        self.views[key].tkraise()
        self._style_modes()
        snap, history = self.monitor.read()
        self.views[key].refresh(snap, history, self.monitor.static)

    def _style_modes(self) -> None:
        for k, b in self.mode_btns.items():
            if k == self.active:
                b.configure(bg=RaceTheme.SIGNAL, fg=_DARK,
                            activebackground=RaceTheme.SIGNAL, activeforeground=_DARK)
            else:
                b.configure(bg=RaceTheme.PANEL, fg=RaceTheme.TEXT,
                            activebackground="#1b2735", activeforeground=RaceTheme.TEXT)

    # ---- actions ---------------------------------------------------------
    def _nitro_purge(self) -> None:
        threading.Thread(target=self.monitor.cleanup_memory, daemon=True).start()
        self.pit_msg.configure(text="Nitro Purge: memory lines cleaned", fg=RaceTheme.SIGNAL)

    def _cooling(self) -> None:
        threading.Thread(target=self.monitor.cooling_mode, daemon=True).start()
        self.pit_msg.configure(text="Cooling System: thermal-safe mode engaged", fg=RaceTheme.CAUTION)

    def _open_settings(self) -> None:
        SettingsWindow(self.root, self.config, self._apply_settings, self.family)

    def _apply_settings(self, cfg: dict) -> None:
        self.config = cfg
        set_accent(cfg.get("accent", "cyan"))
        apply_ttk_theme(self.style, self.family)
        self._style_modes()
        self.monitor.interval = max(0.1, float(cfg.get("monitor_interval", 500)) / 1000.0)
        self._refresh_ms = int(cfg.get("ui_refresh_ms", 200))
        self.pit_msg.configure(text="Settings saved as default", fg=RaceTheme.OPTIMAL)

    # ---- alerts ----------------------------------------------------------
    def _fire_alert(self) -> None:
        if self.config.get("alert_sound", True):
            try:
                import winsound
                winsound.MessageBeep(winsound.MB_ICONHAND)
            except Exception:
                pass
        if self.config.get("taskbar_flash", True):
            try:
                import ctypes
                from ctypes import wintypes

                class FLASHWINFO(ctypes.Structure):
                    _fields_ = [("cbSize", wintypes.UINT), ("hwnd", wintypes.HWND),
                                ("dwFlags", wintypes.DWORD), ("uCount", wintypes.UINT),
                                ("dwTimeout", wintypes.DWORD)]

                info = FLASHWINFO(ctypes.sizeof(FLASHWINFO), self.root.winfo_id(), 0x3 | 0xC, 6, 0)
                ctypes.windll.user32.FlashWindowEx(ctypes.byref(info))
            except Exception:
                pass

    # ---- update loop -----------------------------------------------------
    def _ui_tick(self) -> None:
        if not self.root.winfo_exists():
            return
        snap, history = self.monitor.read()
        self.views[self.active].refresh(snap, history, self.monitor.static)
        self._handle_alert(snap)
        self.root.after(self._refresh_ms, self._ui_tick)

    def _handle_alert(self, snap) -> None:
        cpu_th = float(self.config.get("threshold_cpu", 85))
        ram_th = float(self.config.get("threshold_ram", 85))
        gpu_th = float(self.config.get("threshold_gpu", 90))
        temp_th = float(self.config.get("threshold_temp", 85))
        reasons = []
        if snap.cpu >= cpu_th:
            reasons.append(f"CPU {snap.cpu:.0f}%")
        if snap.ram >= ram_th:
            reasons.append(f"RAM {snap.ram:.0f}%")
        if snap.gpu >= gpu_th:
            reasons.append(f"GPU {snap.gpu:.0f}%")
        if snap.cpu_temp is not None and snap.cpu_temp >= temp_th:
            reasons.append(f"CPU {snap.cpu_temp:.0f}°C")
        if snap.gpu_temp is not None and snap.gpu_temp >= temp_th:
            reasons.append(f"GPU {snap.gpu_temp:.0f}°C")

        if self.config.get("auto_optimize") and snap.ram >= ram_th:
            now = time.time()
            if now - self._auto_purge_last > 30:
                self._auto_purge_last = now
                threading.Thread(target=self.monitor.cleanup_memory, daemon=True).start()
                self.pit_msg.configure(text="Auto Nitro Purge engaged", fg=RaceTheme.SIGNAL)

        if reasons:
            self.banner_label.configure(text="⚠  RED FLAG  —  " + "  •  ".join(reasons))
            self.banner.grid(row=1, column=0, sticky="ew", pady=(0, 8))
            if not self._alerting:
                self._alerting = True
                self._fire_alert()
        elif self._alerting:
            self._alerting = False
            self.banner.grid_remove()

    def _on_close(self) -> None:
        self.monitor.stop()
        self.root.destroy()
