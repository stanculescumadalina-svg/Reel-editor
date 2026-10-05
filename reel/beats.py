"""Lightweight beat tracking (numpy only) so cuts can land on the music.

Onset strength from spectral flux, tempo from autocorrelation, and beat
positions from dynamic programming (Ellis, 2007), the same approach librosa
uses, without the heavy dependency.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np

SR = 22050
HOP = 512
N_FFT = 2048


@dataclass
class BeatGrid:
    bpm: float
    beats: list[float]        # beat times in seconds, from the start of the audio file
    rms: list[float]          # loudness per beat (same length as beats)
    duration: float           # audio length in seconds (0 for a synthetic grid)

    @property
    def period(self) -> float:
        return 60.0 / self.bpm


def load_audio(path: Path) -> np.ndarray:
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
        capture_output=True, check=True,
    ).stdout
    return np.frombuffer(raw, dtype=np.float32)


def onset_envelope(y: np.ndarray) -> np.ndarray:
    if len(y) < N_FFT:
        y = np.pad(y, (0, N_FFT - len(y)))
    n_frames = 1 + (len(y) - N_FFT) // HOP
    idx = np.arange(N_FFT)[None, :] + HOP * np.arange(n_frames)[:, None]
    frames = y[idx] * np.hanning(N_FFT)[None, :]
    mag = np.log1p(100 * np.abs(np.fft.rfft(frames, axis=1)))
    flux = np.maximum(0.0, np.diff(mag, axis=0)).mean(axis=1)
    flux = np.concatenate([[0.0], flux])
    flux -= np.convolve(flux, np.ones(16) / 16, mode="same")  # remove slow trend
    flux = np.maximum(flux, 0.0)
    return flux / (flux.std() + 1e-9)


def estimate_tempo(env: np.ndarray, fps: float, lo: float = 70, hi: float = 180) -> float:
    env = env - env.mean()
    ac = np.correlate(env, env, mode="full")[len(env) - 1:]
    lags = np.arange(int(fps * 60 / hi), int(fps * 60 / lo) + 1)
    lags = lags[lags < len(ac)]
    bpms = 60 * fps / lags
    # Prefer tempos near 120 BPM (log-gaussian, one octave wide) to avoid half/double errors.
    weight = np.exp(-0.5 * (np.log2(bpms / 120.0) / 1.0) ** 2)
    return float(bpms[np.argmax(ac[lags] * weight)])


def track_beats(env: np.ndarray, fps: float, bpm: float, tightness: float = 100.0) -> np.ndarray:
    period = fps * 60.0 / bpm
    local = np.convolve(env, np.exp(-0.5 * ((np.arange(-period, period + 1) * 32 / period) ** 2)), "same")
    score = local.copy()
    backlink = np.full(len(env), -1)
    window = np.arange(-int(round(2 * period)), -int(round(period / 2)) + 1)
    penalty = -tightness * np.log(-window / period) ** 2
    for t in range(len(env)):
        prev = t + window
        ok = prev >= 0
        if not ok.any():
            continue
        cand = score[prev[ok]] + penalty[ok]
        best = int(np.argmax(cand))
        score[t] = local[t] + cand[best]
        backlink[t] = prev[ok][best]
    # Start from the strongest beat in the last period and walk back.
    tail = max(1, int(period))
    t = len(score) - tail + int(np.argmax(score[-tail:]))
    beats = []
    while t >= 0:
        beats.append(t)
        t = backlink[t]
    beats = np.array(beats[::-1])
    # Drop weak leading/trailing beats (silence at the ends of the file).
    strong = local[beats] > 0.5 * np.median(local[beats])
    if strong.any():
        first, last = np.argmax(strong), len(strong) - np.argmax(strong[::-1])
        beats = beats[first:last]
    return beats / fps


def analyze(path: Path) -> BeatGrid:
    y = load_audio(path)
    fps = SR / HOP
    env = onset_envelope(y)
    bpm = estimate_tempo(env, fps)
    beats = track_beats(env, fps, bpm)
    # Refine BPM from the tracked beats themselves; a line fit averages out frame quantization.
    if len(beats) > 8:
        bpm = 60.0 / float(np.polyfit(np.arange(len(beats)), beats, 1)[0])
    rms = []
    for i, b in enumerate(beats):
        end = beats[i + 1] if i + 1 < len(beats) else b + 60 / bpm
        chunk = y[int(b * SR):int(end * SR)]
        rms.append(float(np.sqrt(np.mean(chunk ** 2))) if len(chunk) else 0.0)
    return BeatGrid(bpm=round(bpm, 2), beats=[round(float(b), 3) for b in beats],
                    rms=rms, duration=len(y) / SR)


def fixed_grid(bpm: float, length: float) -> BeatGrid:
    n = int(length * bpm / 60) + 2
    return BeatGrid(bpm=bpm, beats=[round(i * 60 / bpm, 3) for i in range(n)], rms=[1.0] * n, duration=0.0)


def pick_start_beat(grid: BeatGrid, n_beats: int) -> int:
    """Index of the beat where the loudest stretch of `n_beats` begins (the drop/chorus).

    Only bar starts (every 4th beat) are considered so the reel opens on a downbeat.
    """
    if len(grid.beats) <= n_beats:
        return 0
    rms = np.array(grid.rms)
    sums = np.convolve(rms, np.ones(n_beats), "valid")
    candidates = list(range(0, len(sums), 4))
    best = max(candidates, key=lambda i: sums[i])
    # Back up one bar so the energy builds into the reel rather than starting cold.
    return max(0, best - 4) if best >= 4 and sums[best - 4] > 0.85 * sums[best] else best


def beat_times(grid: BeatGrid, start_index: int, count: int) -> list[float]:
    """`count + 1` beat times (relative to the reel start) from `start_index`, extending past the
    end of the song with the average tempo if needed."""
    beats = grid.beats[start_index:start_index + count + 1]
    origin = grid.beats[start_index] if grid.beats else 0.0
    if not beats:
        beats = [origin]
    while len(beats) < count + 1:
        beats.append(beats[-1] + grid.period)
    return [round(b - origin, 4) for b in beats]
