"""Lightweight, dependency-free benchmark (CPU single/multi, memory, disk).

CPU test hashes 64KB blocks with SHA-256; hashlib releases the GIL for blocks
this size, so multiple threads genuinely spread across cores -> a real
multi-core score without the multiprocessing complications.
"""
from __future__ import annotations

import hashlib
import os
import tempfile
import threading
import time

# Large blocks: each SHA-256 call spends milliseconds in native code with the
# GIL released, so the Python loop overhead (and contention from the UI's
# animation threads) is negligible and the single-core number stays honest.
_BLOCK = 4 * 1024 * 1024


def _hash_worker(stop_at, counters, idx):
    data = os.urandom(_BLOCK)
    n = 0
    while time.perf_counter() < stop_at:
        hashlib.sha256(data).digest()
        n += 1
    counters[idx] = n


def _cpu_mbps(threads: int, duration: float) -> float:
    counters = [0] * threads
    stop_at = time.perf_counter() + duration
    ts = [threading.Thread(target=_hash_worker, args=(stop_at, counters, i)) for i in range(threads)]
    t0 = time.perf_counter()
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    elapsed = time.perf_counter() - t0
    return (sum(counters) * _BLOCK) / elapsed / 1e6 if elapsed else 0.0  # MB/s


def _mem_bandwidth(duration: float) -> float:
    size = 64 * 1024 * 1024
    a = bytearray(os.urandom(size))
    copied = 0
    t0 = time.perf_counter()
    stop_at = t0 + duration
    while time.perf_counter() < stop_at:
        _ = bytes(a)            # full memcpy of 64 MB
        copied += size
    elapsed = time.perf_counter() - t0
    return copied / elapsed / 1e9 if elapsed else 0.0  # GB/s


def _disk_speed():
    path = os.path.join(tempfile.gettempdir(), "rtc_benchmark.tmp")
    size = 128 * 1024 * 1024
    buf = os.urandom(8 * 1024 * 1024)
    try:
        t0 = time.perf_counter()
        with open(path, "wb") as f:
            written = 0
            while written < size:
                f.write(buf)
                written += len(buf)
            f.flush()
            os.fsync(f.fileno())
        write_mbs = size / (time.perf_counter() - t0) / 1e6
        t0 = time.perf_counter()
        with open(path, "rb") as f:
            while f.read(8 * 1024 * 1024):
                pass
        read_mbs = size / (time.perf_counter() - t0) / 1e6
        return write_mbs, read_mbs
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def run_benchmark(progress, cores: int) -> dict:
    """progress(stage:str, pct:int) is called between stages. Returns results."""
    progress("Warming up", 2)
    _cpu_mbps(1, 0.4)

    progress("CPU - single core", 8)
    single = _cpu_mbps(1, 3.0)

    progress("CPU - all cores", 38)
    multi = _cpu_mbps(max(1, cores), 3.0)

    progress("Memory bandwidth", 70)
    mem = _mem_bandwidth(2.0)

    progress("Disk speed", 85)
    dw, dr = _disk_speed()

    progress("Done", 100)
    return {
        "cpu_single": single,
        "cpu_multi": multi,
        "parallel": (multi / single) if single else 0.0,
        "mem_gbps": mem,
        "disk_write": dw,
        "disk_read": dr,
        "overall": round(multi),
    }


def tier(overall: float) -> str:
    if overall >= 6000:
        return "EXCELLENT"
    if overall >= 3000:
        return "GREAT"
    if overall >= 1000:
        return "GOOD"
    return "MODEST"
