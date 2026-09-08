"""Centralized, persistent settings for the Race Telemetry Console.

Settings are saved to dashboard_config.json next to the script (or next to the
.exe when frozen) so any change the user makes becomes the new default.
"""
from __future__ import annotations

import json
import os
import sys

DEFAULTS: dict = {
    # alert thresholds (%)
    "threshold_cpu": 85,
    "threshold_ram": 85,
    "threshold_gpu": 90,
    "threshold_temp": 85,
    # timing (milliseconds)
    "monitor_interval": 500,   # how often the background sampler reads metrics
    "ui_refresh_ms": 200,      # how often the UI pulls fresh values
    # toggles
    "startup_sound": True,      # engine sound on open
    "alert_sound": True,        # beep on red-flag alert
    "taskbar_flash": True,      # flash taskbar on alert
    "auto_optimize": False,     # auto memory purge when RAM crosses threshold
    # look
    "accent": "cyan",          # cyan | green | amber | purple | red
}

# Numeric settings get range-clamped on save.
_RANGES = {
    "threshold_cpu": (10, 100), "threshold_ram": (10, 100),
    "threshold_gpu": (10, 100), "threshold_temp": (40, 110),
    "monitor_interval": (100, 5000), "ui_refresh_ms": (50, 2000),
}


def config_path() -> str:
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "dashboard_config.json")


def load() -> dict:
    cfg = dict(DEFAULTS)
    try:
        with open(config_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        for k, v in data.items():
            if k in DEFAULTS:
                cfg[k] = v
        # legacy key migration
        if "auto_optimize_enabled" in data:
            cfg["auto_optimize"] = bool(data["auto_optimize_enabled"])
    except Exception:
        pass
    return _coerce(cfg)


def save(cfg: dict) -> bool:
    merged = dict(DEFAULTS)
    merged.update({k: v for k, v in cfg.items() if k in DEFAULTS})
    try:
        with open(config_path(), "w", encoding="utf-8") as f:
            json.dump(_coerce(merged), f, indent=2)
        return True
    except Exception:
        return False


def _coerce(cfg: dict) -> dict:
    for key, (lo, hi) in _RANGES.items():
        try:
            cfg[key] = max(lo, min(hi, int(float(cfg[key]))))
        except (ValueError, TypeError):
            cfg[key] = DEFAULTS[key]
    for key in ("startup_sound", "alert_sound", "taskbar_flash", "auto_optimize"):
        cfg[key] = bool(cfg.get(key, DEFAULTS[key]))
    if cfg.get("accent") not in ("cyan", "green", "amber", "purple", "red"):
        cfg["accent"] = "cyan"
    return cfg
