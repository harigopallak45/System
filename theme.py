from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk


class RaceTheme:
    """Centralized motorsport color palette and font helpers."""

    BG = "#0b0f14"
    PANEL = "#121821"
    PANEL_ALT = "#0f1620"
    GRID = "#1d2936"

    OPTIMAL = "#00e676"
    CAUTION = "#ffd54f"
    DANGER = "#ff5252"
    SIGNAL = "#40c4ff"
    NEON = "#36f7ff"
    TEXT = "#e9f1ff"
    TEXT_DIM = "#91a4bf"

    @staticmethod
    def usage_color(value: float) -> str:
        if value >= 90:
            return RaceTheme.DANGER
        if value >= 75:
            return RaceTheme.CAUTION
        return RaceTheme.OPTIMAL

    @staticmethod
    def temp_color(celsius) -> str:
        if celsius is None:
            return RaceTheme.TEXT_DIM
        if celsius >= 85:
            return RaceTheme.DANGER
        if celsius >= 70:
            return RaceTheme.CAUTION
        return RaceTheme.OPTIMAL

    @staticmethod
    def dim(hex_color: str, factor: float = 0.45) -> str:
        h = hex_color.lstrip("#")
        r = int(int(h[0:2], 16) * factor)
        g = int(int(h[2:4], 16) * factor)
        b = int(int(h[4:6], 16) * factor)
        return f"#{r:02x}{g:02x}{b:02x}"

    @staticmethod
    def lerp(c1: str, c2: str, t: float) -> str:
        a, b = c1.lstrip("#"), c2.lstrip("#")
        r = round(int(a[0:2], 16) + (int(b[0:2], 16) - int(a[0:2], 16)) * t)
        g = round(int(a[2:4], 16) + (int(b[2:4], 16) - int(a[2:4], 16)) * t)
        bl = round(int(a[4:6], 16) + (int(b[4:6], 16) - int(a[4:6], 16)) * t)
        return f"#{r:02x}{g:02x}{bl:02x}"

    @staticmethod
    def font_family(root: tk.Misc) -> str:
        families = {f.lower() for f in tkfont.families(root)}
        for name in ("Orbitron", "Eurostile", "Bank Gothic", "Rajdhani", "Segoe UI"):
            if name.lower() in families:
                return name
        return "TkDefaultFont"


_anim = {"paused": False}


def set_animations_paused(value: bool) -> None:
    """Freeze all gauge animation loops (used during the benchmark for a clean run)."""
    _anim["paused"] = bool(value)


def animations_paused() -> bool:
    return _anim["paused"]


ACCENTS = {
    "cyan": ("#40c4ff", "#36f7ff"),
    "green": ("#00e676", "#69f0ae"),
    "amber": ("#ffd54f", "#ffe082"),
    "purple": ("#b388ff", "#e1bee7"),
    "red": ("#ff5252", "#ff8a80"),
}


def set_accent(name: str) -> None:
    """Recolor the decorative SIGNAL / NEON accents used across the UI."""
    signal, neon = ACCENTS.get(name, ACCENTS["cyan"])
    RaceTheme.SIGNAL = signal
    RaceTheme.NEON = neon


def apply_ttk_theme(style: ttk.Style, family: str) -> None:
    style.theme_use("clam")

    style.configure("Race.TFrame", background=RaceTheme.BG)
    style.configure("Panel.TFrame", background=RaceTheme.PANEL)
    style.configure("Race.TLabel", background=RaceTheme.BG, foreground=RaceTheme.TEXT, font=(family, 10))
    style.configure("Title.TLabel", background=RaceTheme.PANEL, foreground=RaceTheme.TEXT, font=(family, 13, "bold"))
    style.configure("Value.TLabel", background=RaceTheme.PANEL, foreground=RaceTheme.TEXT, font=(family, 20, "bold"))

    style.configure(
        "Pit.TButton",
        background=RaceTheme.PANEL_ALT,
        foreground=RaceTheme.TEXT,
        bordercolor=RaceTheme.SIGNAL,
        lightcolor=RaceTheme.SIGNAL,
        darkcolor=RaceTheme.PANEL_ALT,
        relief="flat",
        padding=(12, 8),
        font=(family, 10, "bold"),
    )
    style.map(
        "Pit.TButton",
        background=[("active", "#162230")],
        foreground=[("disabled", RaceTheme.TEXT_DIM)],
    )
