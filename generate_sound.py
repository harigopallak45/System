"""Synthesize an engine start (crank -> catch -> rev -> idle) into engine_start.wav.

Pure standard library (wave/struct/math/random) -- no downloads, no packages.
Run once: ``python generate_sound.py``  ->  engine_start.wav
"""
from __future__ import annotations

import math
import random
import struct
import wave

SR = 44100          # sample rate
DUR = 3.0           # seconds
N = int(SR * DUR)
OUT = "engine_start.wav"


def freq_at(t: float) -> float:
    """Instantaneous fundamental frequency = engine RPM curve."""
    if t < 0.8:                       # starter cranking
        return 32.0
    if t < 1.5:                       # catches and revs up
        return 50 + (185 - 50) * ((t - 0.8) / 0.7)
    if t < 2.2:                       # settles back down
        return 185 - (185 - 78) * ((t - 1.5) / 0.7)
    return 78 + 3.0 * math.sin(2 * math.pi * 5 * t)   # idle with vibrato


def main() -> None:
    samples = []
    phase = 0.0
    for i in range(N):
        t = i / SR
        f = freq_at(t)
        phase += 2 * math.pi * f / SR

        # sawtooth-ish engine timbre from summed harmonics
        tone = 0.0
        for k in range(1, 9):
            tone += math.sin(k * phase) / k
        tone *= 0.5

        if t < 0.8:                   # cranking: gated low rumble + grit
            gate = 1.0 if (t * 6) % 1.0 < 0.5 else 0.25
            ramp = min(1.0, t / 0.2)
            crank = 0.6 * math.sin(2 * math.pi * 32 * t) + 0.4 * (random.random() * 2 - 1)
            s = (crank * gate * ramp * 0.5 + tone * 0.05) * 0.7
        else:                          # running engine
            te = t - 0.8
            env = 0.4 + 0.6 * min(1.0, te / 0.15)        # catch swell
            if t > 2.7:
                env *= max(0.0, 1.0 - (t - 2.7) / 0.3)   # fade tail
            noise = (random.random() * 2 - 1) * 0.06
            s = (tone + noise) * env * 0.85

        samples.append(max(-1.0, min(1.0, s)))

    with wave.open(OUT, "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(b"".join(struct.pack("<h", int(s * 32767)) for s in samples))

    print(f"{OUT} written: {len(samples)} samples, {DUR}s")


if __name__ == "__main__":
    main()
