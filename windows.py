from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import appconfig
from theme import RaceTheme


class SettingsWindow(tk.Toplevel):
    """Editable settings; on Save they persist to disk as the new default."""

    def __init__(self, root: tk.Misc, cfg: dict, on_save, family: str):
        super().__init__(root)
        self.on_save = on_save
        self.title("Settings  -  Pit Configuration")
        self.configure(bg=RaceTheme.BG)
        self.resizable(False, False)
        self.transient(root)
        self.vars: dict[str, tk.Variable] = {}

        tk.Label(self, text="PIT CONFIGURATION", bg=RaceTheme.BG, fg=RaceTheme.TEXT,
                 font=(family, 15, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", padx=18, pady=(16, 4))
        tk.Label(self, text="Changes are saved as your default.", bg=RaceTheme.BG, fg=RaceTheme.TEXT_DIM,
                 font=(family, 9)).grid(row=1, column=0, columnspan=2, sticky="w", padx=18, pady=(0, 10))

        r = 2
        self._section("ALERT THRESHOLDS (%)", r, family); r += 1
        r = self._spin("threshold_cpu", "CPU alert at", cfg, r, family, 10, 100)
        r = self._spin("threshold_ram", "RAM alert at", cfg, r, family, 10, 100)
        r = self._spin("threshold_gpu", "GPU alert at", cfg, r, family, 10, 100)
        r = self._spin("threshold_temp", "Temp alert at (°C)", cfg, r, family, 40, 110)

        self._section("TIMING (milliseconds)", r, family); r += 1
        r = self._spin("monitor_interval", "Sensor poll interval", cfg, r, family, 100, 5000, 50)
        r = self._spin("ui_refresh_ms", "Screen refresh", cfg, r, family, 50, 2000, 50)

        self._section("BEHAVIOUR", r, family); r += 1
        r = self._check("startup_sound", "Engine sound on open", cfg, r, family)
        r = self._check("alert_sound", "Beep on red-flag alert", cfg, r, family)
        r = self._check("taskbar_flash", "Flash taskbar on alert", cfg, r, family)
        r = self._check("auto_optimize", "Auto memory purge over RAM limit", cfg, r, family)

        self._section("APPEARANCE", r, family); r += 1
        r = self._accent(cfg, r, family)

        bar = tk.Frame(self, bg=RaceTheme.BG)
        bar.grid(row=r, column=0, columnspan=2, sticky="ew", padx=18, pady=16)
        ttk.Button(bar, text="Save", style="Pit.TButton", command=self._save).pack(side="right", padx=4)
        ttk.Button(bar, text="Reset to Defaults", style="Pit.TButton", command=self._reset).pack(side="right", padx=4)
        ttk.Button(bar, text="Cancel", style="Pit.TButton", command=self.destroy).pack(side="right", padx=4)

        self.grab_set()

    def _section(self, text, r, family):
        tk.Label(self, text=text, bg=RaceTheme.BG, fg=RaceTheme.SIGNAL,
                 font=(family, 10, "bold")).grid(row=r, column=0, columnspan=2, sticky="w", padx=18, pady=(12, 2))

    def _spin(self, key, label, cfg, r, family, lo, hi, step=1):
        tk.Label(self, text=label, bg=RaceTheme.BG, fg=RaceTheme.TEXT, font=(family, 10)).grid(
            row=r, column=0, sticky="w", padx=(28, 12), pady=3)
        var = tk.StringVar(value=str(cfg.get(key)))
        tk.Spinbox(self, from_=lo, to=hi, increment=step, textvariable=var, width=8,
                   bg=RaceTheme.PANEL, fg=RaceTheme.TEXT, insertbackground=RaceTheme.TEXT,
                   buttonbackground=RaceTheme.PANEL, relief="flat", justify="center",
                   font=(family, 10, "bold")).grid(row=r, column=1, sticky="e", padx=(0, 22), pady=3)
        self.vars[key] = var
        return r + 1

    def _check(self, key, label, cfg, r, family):
        var = tk.BooleanVar(value=bool(cfg.get(key)))
        tk.Checkbutton(self, text=label, variable=var, bg=RaceTheme.BG, fg=RaceTheme.TEXT,
                       selectcolor=RaceTheme.PANEL, activebackground=RaceTheme.BG,
                       activeforeground=RaceTheme.TEXT, font=(family, 10), anchor="w").grid(
            row=r, column=0, columnspan=2, sticky="w", padx=(26, 22), pady=2)
        self.vars[key] = var
        return r + 1

    def _accent(self, cfg, r, family):
        tk.Label(self, text="Accent colour", bg=RaceTheme.BG, fg=RaceTheme.TEXT, font=(family, 10)).grid(
            row=r, column=0, sticky="w", padx=(28, 12), pady=3)
        var = tk.StringVar(value=cfg.get("accent", "cyan"))
        om = tk.OptionMenu(self, var, "cyan", "green", "amber", "purple", "red")
        om.configure(bg=RaceTheme.PANEL, fg=RaceTheme.TEXT, activebackground=RaceTheme.PANEL,
                     activeforeground=RaceTheme.TEXT, relief="flat", highlightthickness=0,
                     font=(family, 10, "bold"), width=8)
        om["menu"].configure(bg=RaceTheme.PANEL, fg=RaceTheme.TEXT)
        om.grid(row=r, column=1, sticky="e", padx=(0, 22), pady=3)
        self.vars["accent"] = var
        return r + 1

    def _collect(self) -> dict:
        return {key: var.get() for key, var in self.vars.items()}

    def _reset(self) -> None:
        for key, var in self.vars.items():
            if key in appconfig.DEFAULTS:
                var.set(appconfig.DEFAULTS[key])

    def _save(self) -> None:
        cfg = appconfig._coerce(self._collect())
        appconfig.save(cfg)
        if self.on_save:
            self.on_save(cfg)
        self.destroy()
