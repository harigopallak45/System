from __future__ import annotations

import math
import tkinter as tk

from theme import RaceTheme


class TelemetryGraph(tk.Canvas):
    def __init__(self, parent: tk.Misc, title: str, line_color: str, **kwargs):
        super().__init__(parent, bg=RaceTheme.PANEL, highlightthickness=0, **kwargs)
        self.title = title
        self.line_color = line_color
        self.values: list[float] = []
        self.bind("<Configure>", lambda _: self._draw())

    def set_values(self, values: list[float]) -> None:
        self.values = values[-120:]
        self._draw()

    def _draw(self) -> None:
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 80 or h < 50:
            return

        self.create_rectangle(0, 0, w, h, fill=RaceTheme.PANEL, outline="#1d2d3f", width=1)
        for i in range(1, 5):
            y = h * i / 5
            self.create_line(0, y, w, y, fill=RaceTheme.GRID, width=1)

        self.create_text(10, 12, text=self.title, fill=RaceTheme.TEXT_DIM, anchor="w", font=("Orbitron", 9, "bold"))
        if not self.values:
            return

        step = w / max(1, len(self.values) - 1)
        points = []
        for i, v in enumerate(self.values):
            x = i * step
            y = h - (v / 100.0) * (h - 8) - 4
            points.extend((x, y))

        if len(points) >= 4:
            # filled area under the trace for a soft glow
            area = list(points) + [w, h, 0, h]
            self.create_polygon(*area, fill=RaceTheme.dim(self.line_color, 0.22), outline="")
            self.create_line(*points, fill=self.line_color, width=2, smooth=True)

        self.create_text(w - 10, 12, text=f"{self.values[-1]:.1f}%", fill=self.line_color, anchor="e", font=("Orbitron", 9, "bold"))


class TrackMap(tk.Canvas):
    def __init__(self, parent: tk.Misc, **kwargs):
        super().__init__(parent, bg=RaceTheme.PANEL, highlightthickness=0, **kwargs)
        self.t = 0.0
        self.speed = 0.012
        self.after(33, self._tick)

    def set_speed_factor(self, cpu_percent: float) -> None:
        self.speed = 0.004 + (cpu_percent / 100.0) * 0.02

    def _tick(self) -> None:
        if not self.winfo_exists():
            return
        self.t = (self.t + self.speed) % 1.0
        self._draw()
        self.after(33, self._tick)

    def _track_point(self, t: float, cx: float, cy: float, sx: float, sy: float) -> tuple[float, float]:
        ang = 2 * math.pi * t
        x = cx + sx * math.sin(ang)
        y = cy + sy * math.sin(ang) * math.cos(ang)
        return x, y

    def _draw(self) -> None:
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 80 or h < 50:
            return

        cx, cy = w / 2, h / 2
        sx, sy = w * 0.34, h * 0.36

        pts = []
        for i in range(200):
            x, y = self._track_point(i / 200, cx, cy, sx, sy)
            pts.extend((x, y))

        self.create_line(*pts, fill="#31485f", width=8, smooth=True)
        self.create_line(*pts, fill=RaceTheme.SIGNAL, width=2, smooth=True)

        px, py = self._track_point(self.t, cx, cy, sx, sy)
        self.create_oval(px - 8, py - 8, px + 8, py + 8, fill=RaceTheme.OPTIMAL, outline=RaceTheme.NEON, width=2)
        self.create_text(10, 12, text="TRACK MAP", fill=RaceTheme.TEXT_DIM, anchor="w", font=("Orbitron", 9, "bold"))
