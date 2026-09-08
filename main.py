from __future__ import annotations

import os
import sys
import tkinter as tk
from tkinter import ttk

import appconfig
from dashboard import MotorsportDashboard
from theme import RaceTheme, apply_ttk_theme, set_accent


def _resource_path(name: str) -> str:
    """Path to a bundled resource, works in dev and in a PyInstaller .exe."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


def play_startup_sound() -> None:
    """Fire the engine-start sound (async, non-blocking). Windows only."""
    if sys.platform != "win32":
        return
    try:
        import winsound

        path = _resource_path("engine_start.wav")
        if os.path.exists(path):
            winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
    except Exception:
        pass


class StartupSequence(tk.Toplevel):
    def __init__(self, root: tk.Tk, on_done):
        super().__init__(root)
        self.root = root
        self.on_done = on_done
        self.progress = 0

        self.overrideredirect(True)
        self.configure(bg=RaceTheme.BG)
        self.attributes("-topmost", True)

        width, height = 520, 230
        x = (self.winfo_screenwidth() - width) // 2
        y = (self.winfo_screenheight() - height) // 2
        self.geometry(f"{width}x{height}+{x}+{y}")

        family = RaceTheme.font_family(root)
        style = ttk.Style(self)
        apply_ttk_theme(style, family)
        style.configure("Startup.Horizontal.TProgressbar", troughcolor="#0f1520", background=RaceTheme.SIGNAL, bordercolor="#1f2a38")

        wrap = tk.Frame(self, bg=RaceTheme.BG)
        wrap.pack(fill="both", expand=True, padx=24, pady=24)

        tk.Label(
            wrap,
            text="INITIALIZING RACE TELEMETRY",
            bg=RaceTheme.BG,
            fg=RaceTheme.TEXT,
            font=(family, 18, "bold"),
        ).pack(anchor="w", pady=(8, 16))

        self.stage = tk.Label(wrap, text="Booting sensors...", bg=RaceTheme.BG, fg=RaceTheme.TEXT_DIM, font=(family, 10))
        self.stage.pack(anchor="w", pady=(0, 16))

        self.bar = ttk.Progressbar(wrap, mode="determinate", maximum=100, style="Startup.Horizontal.TProgressbar")
        self.bar.pack(fill="x")

        self.percent = tk.Label(wrap, text="0%", bg=RaceTheme.BG, fg=RaceTheme.SIGNAL, font=(family, 10, "bold"))
        self.percent.pack(anchor="e", pady=(8, 0))

        self.after(40, self._tick)

    def _tick(self):
        self.progress += 2
        self.bar.configure(value=self.progress)
        self.percent.configure(text=f"{self.progress}%")

        if self.progress < 30:
            self.stage.configure(text="Synchronizing engine channels...")
        elif self.progress < 65:
            self.stage.configure(text="Calibrating pit wall displays...")
        elif self.progress < 95:
            self.stage.configure(text="Verifying telemetry link integrity...")
        else:
            self.stage.configure(text="Race systems online")

        if self.progress >= 100:
            self.destroy()
            self.on_done()
            return

        self.after(45, self._tick)


def run() -> None:
    cfg = appconfig.load()
    set_accent(cfg.get("accent", "cyan"))

    root = tk.Tk()
    root.withdraw()

    if cfg.get("startup_sound", True):
        play_startup_sound()  # engine fires up as the splash appears

    def start_dashboard() -> None:
        root.deiconify()
        MotorsportDashboard(root)

    StartupSequence(root, start_dashboard)
    root.mainloop()


if __name__ == "__main__":
    run()
