from __future__ import annotations

import math
import tkinter as tk

from theme import RaceTheme, animations_paused


class _Animated(tk.Canvas):
    """Canvas that eases a single value toward a target at ~60fps and only
    repaints while it is actually moving (idle = no redraws)."""

    def __init__(self, parent: tk.Misc, **kwargs):
        super().__init__(parent, bg=RaceTheme.PANEL, highlightthickness=0, **kwargs)
        self.target = 0.0
        self.display = 0.0
        self.bind("<Configure>", lambda _: self._draw())
        self.after(16, self._animate)

    def set_value(self, value: float) -> None:
        self.target = max(0.0, min(100.0, value))

    def _animate(self) -> None:
        if not self.winfo_exists():
            return
        if not animations_paused() and abs(self.display - self.target) > 0.05:
            self.display += (self.target - self.display) * 0.18
            self._draw()
        self.after(16, self._animate)

    def _draw(self) -> None:  # overridden
        pass


class TachometerGauge(_Animated):
    def __init__(self, parent: tk.Misc, title: str, **kwargs):
        super().__init__(parent, **kwargs)
        self.title = title

    def _draw(self) -> None:
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 50 or h < 50:
            return

        cx, cy = w / 2, h * 0.62
        r = min(w, h) * 0.38
        start_deg, end_deg = 210, -30
        glow = RaceTheme.usage_color(self.display)

        self.create_oval(cx - r - 14, cy - r - 14, cx + r + 14, cy + r + 14, outline="#10202f", width=3)
        # base track
        self.create_arc(cx - r, cy - r, cx + r, cy + r, start=start_deg, extent=end_deg - start_deg,
                        style="arc", outline="#263547", width=14)
        # value arc with layered glow
        extent = (end_deg - start_deg) * (self.display / 100.0)
        self.create_arc(cx - r, cy - r, cx + r, cy + r, start=start_deg, extent=extent,
                        style="arc", outline=RaceTheme.dim(glow, 0.4), width=20)
        self.create_arc(cx - r, cy - r, cx + r, cy + r, start=start_deg, extent=extent,
                        style="arc", outline=glow, width=12)

        for p in range(0, 101, 10):
            angle = math.radians(start_deg + (end_deg - start_deg) * p / 100)
            inner, outer = r - 18, r + 2
            x1, y1 = cx + inner * math.cos(angle), cy - inner * math.sin(angle)
            x2, y2 = cx + outer * math.cos(angle), cy - outer * math.sin(angle)
            tick = RaceTheme.DANGER if p >= 90 else RaceTheme.CAUTION if p >= 75 else RaceTheme.TEXT_DIM
            self.create_line(x1, y1, x2, y2, fill=tick, width=2)

        needle = math.radians(start_deg + (end_deg - start_deg) * self.display / 100)
        nx, ny = cx + (r - 25) * math.cos(needle), cy - (r - 25) * math.sin(needle)
        self.create_line(cx, cy, nx, ny, fill=glow, width=4)
        self.create_oval(cx - 9, cy - 9, cx + 9, cy + 9, fill=glow, outline=RaceTheme.NEON)

        self.create_text(w / 2, h * 0.12, text=self.title, fill=RaceTheme.TEXT_DIM, font=("Orbitron", 11, "bold"))
        self.create_text(w / 2, h * 0.82, text=f"{self.display:05.1f}%", fill=RaceTheme.TEXT, font=("Orbitron", 24, "bold"))
        self.create_text(w / 2, h * 0.92, text="Engine RPM", fill=RaceTheme.SIGNAL, font=("Orbitron", 10))


class VerticalGauge(_Animated):
    def __init__(self, parent: tk.Misc, title: str, subtitle: str, **kwargs):
        super().__init__(parent, **kwargs)
        self.title = title
        self.subtitle = subtitle

    def _draw(self) -> None:
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 40 or h < 40:
            return

        color = RaceTheme.usage_color(self.display)
        x0, x1 = w * 0.32, w * 0.68
        y0, y1 = h * 0.16, h * 0.86

        self.create_rectangle(x0 - 8, y0 - 8, x1 + 8, y1 + 8, outline="#1d2d3f", width=2)
        self.create_rectangle(x0, y0, x1, y1, fill="#0d1118", outline="#1f2a38", width=2)

        fill_h = (y1 - y0) * (self.display / 100.0)
        top = y1 - fill_h
        # gradient fill: dim at base -> bright at the meniscus
        y = y1 - 2
        while y > top:
            t = (y1 - y) / max(1.0, (y1 - top))
            self.create_line(x0 + 2, y, x1 - 2, y, fill=RaceTheme.lerp(RaceTheme.dim(color, 0.5), color, t))
            y -= 2
        if fill_h > 3:
            self.create_line(x0 + 2, top, x1 - 2, top, fill=RaceTheme.NEON, width=2)
        if self.display >= 75:
            self.create_rectangle(x0 - 4, y0 - 4, x1 + 4, y1 + 4, outline=color, width=1)

        self.create_text(w / 2, h * 0.06, text=self.title, fill=RaceTheme.TEXT_DIM, font=("Orbitron", 10, "bold"))
        self.create_text(w / 2, h * 0.93, text=f"{self.display:04.1f}%", fill=RaceTheme.TEXT, font=("Orbitron", 12, "bold"))
        self.create_text(w / 2, h * 0.99, text=self.subtitle, fill=RaceTheme.SIGNAL, font=("Orbitron", 8), anchor="s")


class GearIndicator(tk.Canvas):
    def __init__(self, parent: tk.Misc, **kwargs):
        super().__init__(parent, bg=RaceTheme.PANEL, highlightthickness=0, **kwargs)
        self.cpu = 0.0
        self.bind("<Configure>", lambda _: self._draw())

    @staticmethod
    def map_gear(cpu: float) -> str:
        if cpu < 20:
            return "N"
        if cpu < 40:
            return "1"
        if cpu < 60:
            return "2"
        if cpu < 75:
            return "3"
        if cpu < 90:
            return "4"
        return "5"

    def set_cpu(self, cpu: float) -> None:
        self.cpu = max(0.0, min(100.0, cpu))
        self._draw()

    def _draw(self) -> None:
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        gear = self.map_gear(self.cpu)
        color = RaceTheme.usage_color(self.cpu)

        self.create_rectangle(10, 10, w - 10, h - 10, outline="#1f2a38", width=2)
        self.create_rectangle(14, 14, w - 14, h - 14, outline=color, width=2)
        self.create_text(w / 2, h * 0.3, text="GEAR", fill=RaceTheme.TEXT_DIM, font=("Orbitron", 10, "bold"))
        self.create_text(w / 2, h * 0.66, text=gear, fill=color, font=("Orbitron", max(10, int(h * 0.40)), "bold"))


class CoreBars(tk.Canvas):
    """One vertical bar per logical CPU core, eased."""

    def __init__(self, parent: tk.Misc, **kwargs):
        super().__init__(parent, bg=RaceTheme.PANEL, highlightthickness=0, **kwargs)
        self.values: list[float] = []
        self.display: list[float] = []
        self.bind("<Configure>", lambda _: self._draw())
        self.after(33, self._animate)

    def set_values(self, values: list[float]) -> None:
        self.values = list(values)
        if len(self.display) != len(self.values):
            self.display = list(self.values)

    def _animate(self) -> None:
        if not self.winfo_exists():
            return
        if not animations_paused():
            moved = False
            for i in range(min(len(self.display), len(self.values))):
                if abs(self.display[i] - self.values[i]) > 0.5:
                    self.display[i] += (self.values[i] - self.display[i]) * 0.25
                    moved = True
            if moved:
                self._draw()
        self.after(33, self._animate)

    def _draw(self) -> None:
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 60 or h < 40 or not self.display:
            return
        self.create_text(10, 12, text="CORE LOAD", fill=RaceTheme.TEXT_DIM, anchor="w", font=("Orbitron", 9, "bold"))
        n = len(self.display)
        pad, top, bottom = 8, 26, h - 18
        gap = 4
        bw = (w - pad * 2 - gap * (n - 1)) / n
        for i, v in enumerate(self.display):
            x0 = pad + i * (bw + gap)
            x1 = x0 + bw
            color = RaceTheme.usage_color(v)
            self.create_rectangle(x0, top, x1, bottom, outline="#1f2a38", fill="#0d1118")
            fh = (bottom - top) * (v / 100.0)
            self.create_rectangle(x0 + 1, bottom - fh, x1 - 1, bottom - 1, fill=color, outline="")
            self.create_text((x0 + x1) / 2, h - 8, text=str(i), fill=RaceTheme.TEXT_DIM, font=("Orbitron", 7))


class ProcessMonitor(tk.Canvas):
    """Top processes by RAM, drawn as name + relative bar + MB."""

    def __init__(self, parent: tk.Misc, **kwargs):
        super().__init__(parent, bg=RaceTheme.PANEL, highlightthickness=0, **kwargs)
        self.procs: list[tuple[str, float]] = []
        self.bind("<Configure>", lambda _: self._draw())

    def set_procs(self, procs: list[tuple[str, float]]) -> None:
        self.procs = procs
        self._draw()

    def _draw(self) -> None:
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 80 or h < 40:
            return
        self.create_text(10, 12, text="TOP CONSUMERS (RAM)", fill=RaceTheme.TEXT_DIM, anchor="w", font=("Orbitron", 9, "bold"))
        if not self.procs:
            return
        peak = max(mb for _, mb in self.procs) or 1.0
        row_h = (h - 30) / max(1, len(self.procs))
        for i, (name, mb) in enumerate(self.procs):
            y = 28 + i * row_h
            label = name[:18]
            self.create_text(10, y + row_h * 0.32, text=label, fill=RaceTheme.TEXT, anchor="w", font=("Orbitron", 8))
            self.create_text(w - 10, y + row_h * 0.32, text=f"{mb:,.0f} MB", fill=RaceTheme.SIGNAL, anchor="e", font=("Orbitron", 8, "bold"))
            bar_y = y + row_h * 0.62
            self.create_line(10, bar_y, w - 10, bar_y, fill="#1f2a38", width=3)
            frac = mb / peak
            self.create_line(10, bar_y, 10 + (w - 20) * frac, bar_y, fill=RaceTheme.NEON, width=3)


class NeonCard(tk.Frame):
    def __init__(self, parent: tk.Misc, title: str):
        super().__init__(parent, bg=RaceTheme.PANEL, highlightthickness=0)
        self.configure(bd=0)
        self._edge = tk.Frame(self, bg="#1d2d3f", height=2)
        self._edge.pack(side="top", fill="x")
        self._title = tk.Label(self, text=title, bg=RaceTheme.PANEL, fg=RaceTheme.TEXT_DIM, font=("Orbitron", 10, "bold"))
        self._title.pack(anchor="w", padx=12, pady=(8, 0))

    def set_alert(self, value: float) -> None:
        self._edge.configure(bg=RaceTheme.usage_color(value))
