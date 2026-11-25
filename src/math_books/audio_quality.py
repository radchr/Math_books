"""Non-mutating PCM16 acoustic screening for future lessons.

20 ms RMS activity is energy-based, NOT VAD. RMS dBFS is neither LUFS nor
true peak. Thresholds flag gross defects or request listening; they cannot
certify pronunciation, intelligibility or perceptual loudness.
"""

from __future__ import annotations

import hashlib
import json
import math
import wave
from pathlib import Path

import numpy as np

ACOUSTIC_POLICY_VERSION = 1


def policy_profile() -> dict:
    """JSON-safe thresholds and identity for recomputed acoustic evidence."""
    configuration = {
        "version": ACOUSTIC_POLICY_VERSION,
        "supported_format": "uncompressed little-endian signed PCM16 WAV",
        "activity_kind": "energy-based frame RMS; not VAD",
        "frame_s": 0.02,
        "activity_threshold_dbfs": -50.0,
        "quiet_rms_dbfs": -35.0,
        "edge_pause_review_s": 0.75,
        "internal_pause_review_s": 2.0,
        "near_full_scale_pcm16": 32760,
        "clipped_fraction_fail": 0.01,
        "absolute_dc_offset_review": 0.02,
        "dbfs_reference": 32768,
    }
    digest = hashlib.sha256(json.dumps(configuration, sort_keys=True).encode()).hexdigest()
    return {**configuration, "configuration_sha256": digest}


def _dbfs(amplitude: float) -> float | None:
    # JSON null describes zero-energy (-infinity dBFS) without nonfinite JSON.
    return 20 * math.log10(amplitude) if amplitude > 0 else None


def analyze_audio(path: Path) -> dict:
    """Measure bytes without modifying audio; only pass has ``ok: true``.

    >=1% samples within eight PCM16 counts of either full-scale rail fails.
    This is a sample-occupancy heuristic, not a claim about true-peak clipping.
    Undefined metrics are null. Unsupported or truncated files fail explicitly.
    """
    policy = policy_profile()
    report: dict = dict.fromkeys(
        [
            "sample_rate",
            "channels",
            "duration",
            "peak_dbfs",
            "rms_dbfs",
            "dc_offset",
            "clipped_fraction",
            "leading_silence_s",
            "trailing_silence_s",
            "max_internal_pause_s",
            "active_fraction",
        ]
    )
    report.update(status="fail", ok=False, issues=[], warnings=[], policy=policy)
    issues: list[str] = report["issues"]
    warnings: list[str] = report["warnings"]
    try:
        with wave.open(str(path), "rb") as source:
            rate, channels, count = source.getframerate(), source.getnchannels(), source.getnframes()
            report.update(sample_rate=rate, channels=channels)
            if source.getsampwidth() != 2 or source.getcomptype() != "NONE":
                issues.append("Unsupported audio format: uncompressed PCM16 WAV is required")
                return report
            if rate <= 0 or channels <= 0 or count <= 0:
                issues.append("Empty audio or invalid PCM dimensions")
                return report
            raw = source.readframes(count)
            if len(raw) != count * channels * 2:
                issues.append("Truncated WAV: PCM bytes do not match declared frame count")
                return report
    except (OSError, EOFError, wave.Error, ValueError):
        issues.append("Unreadable or invalid PCM16 WAV")
        return report

    pcm = np.frombuffer(raw, dtype="<i2").reshape(count, channels).astype(np.float64)
    samples = pcm / 32768.0
    duration = count / rate
    peak = float(np.max(np.abs(samples)))
    rms = float(np.sqrt(np.mean(samples * samples)))
    channel_dc = np.mean(samples, axis=0)
    dc = float(channel_dc[np.argmax(np.abs(channel_dc))])
    clipped = float(np.mean(np.abs(pcm) >= policy["near_full_scale_pcm16"]))

    frame_size = max(1, round(rate * policy["frame_s"]))
    starts = np.arange(0, count, frame_size)
    sizes = np.minimum(frame_size, count - starts)
    sample_energy = np.mean(samples * samples, axis=1)
    energies = np.add.reduceat(sample_energy, starts) / sizes
    active = energies >= 10 ** (policy["activity_threshold_dbfs"] / 10)
    active_indices = np.flatnonzero(active)
    if active_indices.size:
        first, last = int(active_indices[0]), int(active_indices[-1])
        leading = int(np.sum(sizes[:first])) / rate
        trailing = int(np.sum(sizes[last + 1 :])) / rate
        longest_samples = pause_samples = 0
        for index in range(first, last + 1):
            pause_samples = 0 if active[index] else pause_samples + int(sizes[index])
            longest_samples = max(longest_samples, pause_samples)
        longest = longest_samples / rate
    else:
        # With no detected activity both edge spans cover the entire clip;
        # there is no bounded internal pause.
        leading = trailing = duration
        longest = 0.0
    report.update(
        duration=duration,
        peak_dbfs=_dbfs(peak),
        rms_dbfs=_dbfs(rms),
        dc_offset=dc,
        clipped_fraction=clipped,
        leading_silence_s=leading,
        trailing_silence_s=trailing,
        max_internal_pause_s=longest,
        active_fraction=int(np.sum(sizes[active])) / count,
    )
    if peak == 0:
        issues.append("Silent PCM: every sample is zero")
    if clipped >= policy["clipped_fraction_fail"]:
        issues.append("Severe near-full-scale sample occupancy (at least 1%); inspect clipping")
    if rms > 0 and 20 * math.log10(rms) < policy["quiet_rms_dbfs"]:
        warnings.append("Low RMS level; listen before approving")
    if max(leading, trailing) > policy["edge_pause_review_s"]:
        warnings.append("Excessive energy-based leading or trailing silence; inspect timing")
    if longest > policy["internal_pause_review_s"]:
        warnings.append("Long internal energy-based pause; inspect narration timing")
    if abs(dc) > policy["absolute_dc_offset_review"]:
        warnings.append("Large DC offset; inspect recording")
    status = "fail" if issues else "needs_review" if warnings else "pass"
    report.update(status=status, ok=status == "pass")
    return report
