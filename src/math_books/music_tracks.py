"""Reusable licensed music bank (assets/music/) with procedural, AI model (Lyria / ACE-Step), and import support."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import subprocess
import tempfile
import wave
from pathlib import Path
from typing import Any

import httpx
import numpy as np
from dotenv import load_dotenv

from math_books.media_io import atomic_json, wav_duration

MUSIC_BACKENDS = ("procedural", "musicgen", "ace_step", "lyria")
PROCEDURAL_PRESETS = ("calm", "energetic")
_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def music_dir(root: Path) -> Path:
    return root / "assets" / "music"


def load_music_catalog(root: Path) -> dict[str, dict[str, Any]]:
    manifest_path = music_dir(root) / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Missing music catalog: {manifest_path}")
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    tracks = raw.get("tracks") if isinstance(raw, dict) else None
    if not isinstance(tracks, list) or not tracks:
        raise ValueError("Music catalog must contain a non-empty tracks list")
    catalog: dict[str, dict[str, Any]] = {}
    for entry in tracks:
        if not isinstance(entry, dict):
            raise ValueError("Music track entry must be an object")
        tid = entry.get("id")
        if not isinstance(tid, str) or not tid.strip() or tid in catalog:
            raise ValueError(f"Invalid or duplicate music track id: {tid!r}")
        for field in ("file", "title", "license", "author", "sha256"):
            if not isinstance(entry.get(field), str) or not entry[field].strip():
                raise ValueError(f"Music track {tid!r} missing required field {field!r}")
        catalog[tid] = entry
    return catalog


def query_music_catalog(
    root: Path,
    *,
    mood: str | None = None,
    tag: str | None = None,
    source: str | None = None,
) -> list[dict[str, Any]]:
    """Filter reusable tracks in assets/music/manifest.json by mood, tag, or source."""
    catalog = load_music_catalog(root)
    results: list[dict[str, Any]] = []
    for tid in sorted(catalog):
        item = catalog[tid]
        if mood is not None and item.get("mood") != mood:
            continue
        if source is not None and item.get("source") != source:
            continue
        if tag is not None and tag not in item.get("tags", []):
            continue
        results.append(item)
    return results


def resolve_music_track(root: Path, track_id: str) -> tuple[Path, dict[str, Any]]:
    """Validate track provenance (file exists, inside assets/music, matching SHA-256) and return (path, meta)."""
    catalog = load_music_catalog(root)
    if track_id not in catalog:
        available = ", ".join(sorted(catalog))
        raise ValueError(f"Unknown music track {track_id!r}. Available: {available}")
    entry = catalog[track_id]
    base = music_dir(root).resolve()
    track_path = (base / entry["file"]).resolve()
    if not track_path.is_relative_to(base) or not track_path.is_file():
        raise FileNotFoundError(f"Music track file missing or escapes assets/music: {entry['file']}")
    actual_sha = hashlib.sha256(track_path.read_bytes()).hexdigest()
    if actual_sha != entry["sha256"]:
        raise ValueError(f"Music track checksum mismatch for {track_id!r}")
    return track_path, entry


def _normalize_to_wav(source_path: Path, out_wav: Path, *, sample_rate: int = 24000) -> None:
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-v",
        "error",
        "-i",
        str(source_path),
        "-ac",
        "1",
        "-ar",
        str(sample_rate),
        "-sample_fmt",
        "s16",
        "-f",
        "wav",
        str(out_wav),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=60)


def _register_track_entry(
    root: Path,
    entry: dict[str, Any],
    *,
    staged_wav: Path | None = None,
    dest_wav: Path | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    from math_books.media_io import audio_lock

    out_dir = music_dir(root)
    out_dir.mkdir(parents=True, exist_ok=True)
    with audio_lock(out_dir):
        manifest_path = out_dir / "manifest.json"
        if manifest_path.is_file():
            raw = json.loads(manifest_path.read_text(encoding="utf-8"))
            tracks = list(raw.get("tracks", []))
        else:
            tracks = []
        exists = any(t.get("id") == entry["id"] for t in tracks)
        if exists and not overwrite:
            raise FileExistsError(f"Music track {entry['id']!r} already exists; pass --overwrite to replace")
        if dest_wav is not None and dest_wav.exists() and not overwrite:
            raise FileExistsError(f"Music track file already exists: {dest_wav}; pass --overwrite to replace")
        for key in ("id", "file", "title", "license", "author", "sha256"):
            val = entry.get(key)
            if not isinstance(val, str) or not val.strip():
                raise ValueError(f"Music track entry requires non-empty {key!r}")
        if staged_wav is not None and dest_wav is not None:
            staged_wav.replace(dest_wav)
        tracks = [t for t in tracks if t.get("id") != entry["id"]]
        tracks.append(entry)
        tracks.sort(key=lambda t: str(t["id"]))
        atomic_json(manifest_path, {"schema_version": 1, "tracks": tracks})
        return entry


def synthesize_procedural_wav(
    out_wav: Path,
    *,
    preset: str = "energetic",
    bpm: float = 124.0,
    duration_s: float = 16.0,
    sample_rate: int = 24000,
) -> float:
    """Generate a seamless CC0-1.0 procedural WAV track ('calm' or 'energetic') using numpy."""
    if preset not in PROCEDURAL_PRESETS:
        raise ValueError(f"Unsupported procedural preset {preset!r}; choose {', '.join(PROCEDURAL_PRESETS)}")
    if not (60.0 <= bpm <= 180.0) or not (4.0 <= duration_s <= 120.0):
        raise ValueError("bpm must be 60..180 and duration_s must be 4..120")

    out_wav.parent.mkdir(parents=True, exist_ok=True)
    if preset == "calm":
        n = int(round(sample_rate * duration_s))
        t = np.linspace(0, duration_s, n, endpoint=False)
        chords = [
            (220.0, 261.63, 329.63),
            (174.61, 220.0, 261.63),
            (261.63, 329.63, 392.00),
            (196.00, 246.94, 293.66),
        ]
        sig = np.zeros(n, dtype=np.float64)
        seg = n // len(chords)
        for idx, freqs in enumerate(chords):
            s0, s1 = idx * seg, (idx + 1) * seg if idx < len(chords) - 1 else n
            lt = t[s0:s1] - t[s0]
            span = (s1 - s0) / sample_rate
            env = np.sin(np.pi * lt / span) ** 0.45
            pad = sum(np.sin(2 * np.pi * f * lt) + 0.25 * np.sin(2 * np.pi * (f * 2) * lt) for f in freqs)
            pulse = 0.85 + 0.15 * np.sin(2 * np.pi * (bpm / 60.0) * lt)
            sig[s0:s1] = pad * env * pulse
        sig = sig / max(1e-9, float(np.max(np.abs(sig)))) * 0.25
    else:
        beat_s = 60.0 / bpm
        total_beats = max(8, int(round(duration_s / beat_s / 4)) * 4)
        actual_dur = total_beats * beat_s
        n = int(round(sample_rate * actual_dur))
        rng = np.random.default_rng(42)
        sig = np.zeros(n, dtype=np.float64)
        for b in range(total_beats):
            s0 = int(round(b * beat_s * sample_rate))
            klen = min(int(0.18 * sample_rate), n - s0)
            kt = np.arange(klen) / sample_rate
            freq = 48.0 + 115.0 * np.exp(-kt * 32.0)
            phase = 2 * np.pi * np.cumsum(freq) / sample_rate
            sig[s0 : s0 + klen] += 0.55 * np.sin(phase) * np.exp(-kt * 16.0)
        for b in range(1, total_beats, 2):
            s0 = int(round(b * beat_s * sample_rate))
            slen = min(int(0.14 * sample_rate), n - s0)
            st = np.arange(slen) / sample_rate
            tone = np.sin(2 * np.pi * 190.0 * st) * np.exp(-st * 30.0)
            sig[s0 : s0 + slen] += (0.22 * rng.normal(0, 1, slen) + 0.18 * tone) * np.exp(-st * 24.0)
        for step in range(total_beats * 4):
            s0 = int(round(step * (beat_s / 4.0) * sample_rate))
            hlen = min(int(0.04 * sample_rate), n - s0)
            ht = np.arange(hlen) / sample_rate
            accent = 0.14 if step % 4 == 2 else (0.06 if step % 2 == 0 else 0.04)
            hp = np.diff(rng.normal(0, 1, hlen), prepend=0)
            sig[s0 : s0 + hlen] += accent * hp * np.exp(-ht * 65.0)
        bass_roots = [110.0, 87.31, 130.81, 98.0]
        for step in range(total_beats * 2):
            s0 = int(round(step * (beat_s / 2.0) * sample_rate))
            blen = min(int(beat_s * 0.46 * sample_rate), n - s0)
            bt = np.arange(blen) / sample_rate
            f = bass_roots[(step // 16) % 4] * (2.0 if step % 2 == 1 else 1.0)
            wave_b = sum((1.0 / k) * np.sin(2 * np.pi * f * k * bt) for k in range(1, 5))
            sig[s0 : s0 + blen] += 0.16 * wave_b * np.exp(-bt * 6.5) * (1.0 - np.exp(-bt * 120.0))
        arp_chords = [
            [440.0, 523.25, 659.25, 783.99],
            [349.23, 440.0, 523.25, 659.25],
            [523.25, 659.25, 783.99, 987.77],
            [392.0, 493.88, 587.33, 783.99],
        ]
        pattern = [0, 1, 2, 3, 2, 1, 3, 2]
        for step in range(0, total_beats * 4, 2):
            s0 = int(round(step * (beat_s / 4.0) * sample_rate))
            alen = min(int(beat_s * 0.42 * sample_rate), n - s0)
            at = np.arange(alen) / sample_rate
            f = arp_chords[(step // 32) % 4][pattern[(step // 2) % len(pattern)]]
            pluck = (
                np.sin(2 * np.pi * f * at)
                + 0.35 * np.sin(2 * np.pi * 2 * f * at)
                + 0.12 * np.sin(2 * np.pi * 3 * f * at)
            )
            sig[s0 : s0 + alen] += 0.13 * pluck * np.exp(-at * 11.0) * (1.0 - np.exp(-at * 200.0))
        sig = np.tanh(sig * 1.15)
        sig = sig / max(1e-9, float(np.max(np.abs(sig)))) * 0.65

    pcm = (sig * 32767).astype("<i2").tobytes()
    with wave.open(str(out_wav), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)
    return wav_duration(out_wav)


def synthesize_musicgen_wav(
    prompt: str,
    out_wav: Path,
    *,
    hf_token: str | None = None,
    space: str = "facebook/MusicGen",
) -> float:
    """Generate live instrumental music via public Hugging Face facebook/MusicGen Space."""
    from gradio_client import Client

    client = Client(space, token=hf_token)
    result = client.predict(prompt, None, api_name="/predict_batched")
    audio_path = result[0] if isinstance(result, (list, tuple)) and result else result
    if isinstance(audio_path, dict):
        audio_path = audio_path.get("path")
    if not isinstance(audio_path, (str, Path)) or not Path(audio_path).is_file():
        raise RuntimeError(f"MusicGen returned unexpected audio result: {type(result).__name__}")
    _normalize_to_wav(Path(audio_path), out_wav)
    return wav_duration(out_wav)


def synthesize_ace_step_wav(
    prompt: str,
    out_wav: Path,
    *,
    duration_s: float = 30.0,
    hf_token: str | None = None,
    space: str = "ACE-Step/ACE-Step",
    infer_steps: int = 40,
) -> float:
    """Generate live instrumental music via public Hugging Face ACE-Step Space (free with HF-TOKEN)."""
    from gradio_client import Client

    client = Client(space, token=hf_token)
    result = client.predict(
        audio_duration=float(duration_s),
        prompt=prompt,
        lyrics="[instrumental]",
        infer_step=int(infer_steps),
        api_name="/__call__",
    )
    audio_path = result[0] if isinstance(result, (list, tuple)) and result else result
    if isinstance(audio_path, dict):
        audio_path = audio_path.get("path")
    if not isinstance(audio_path, (str, Path)) or not Path(audio_path).is_file():
        raise RuntimeError(f"ACE-Step returned unexpected audio result: {type(result).__name__}")
    _normalize_to_wav(Path(audio_path), out_wav)
    return wav_duration(out_wav)


def synthesize_lyria_wav(
    prompt: str,
    out_wav: Path,
    *,
    api_key: str,
    model: str = "lyria-3-clip-preview",
) -> float:
    """Generate music via Gemini Lyria API (requires paid billing on GEMINI_API_KEY)."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    resp = httpx.post(
        url,
        headers={"x-goog-api-key": api_key},
        json={"contents": [{"parts": [{"text": prompt}]}]},
        timeout=120,
    )
    if resp.status_code != 200:
        detail = resp.text.replace(api_key, "[REDACTED]")[:400]
        raise RuntimeError(f"Lyria music generation failed ({resp.status_code}): {detail}")
    data = resp.json()
    candidates = data.get("candidates") if isinstance(data, dict) else None
    first_candidate = candidates[0] if isinstance(candidates, list) and candidates else None
    content = first_candidate.get("content") if isinstance(first_candidate, dict) else None
    parts = content.get("parts") if isinstance(content, dict) else None
    audio_bytes = None
    if isinstance(parts, list):
        for part in parts:
            if isinstance(part, dict) and isinstance(part.get("inlineData"), dict) and "data" in part["inlineData"]:
                audio_bytes = base64.b64decode(part["inlineData"]["data"])
                break
    if audio_bytes is None:
        raise RuntimeError("No audio inlineData returned by Lyria")
    with tempfile.TemporaryDirectory() as tmp:
        raw_file = Path(tmp) / "lyria_raw.bin"
        raw_file.write_bytes(audio_bytes)
        _normalize_to_wav(raw_file, out_wav)
    return wav_duration(out_wav)


def generate_music_track(
    root: Path,
    *,
    track_id: str,
    backend: str,
    title: str | None = None,
    prompt: str = "",
    preset: str = "energetic",
    bpm: float = 124.0,
    duration_s: float = 30.0,
    mood: str = "energetic",
    tags: list[str] | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Generate a reusable track (via code or AI model) and register it in assets/music/manifest.json."""
    if not _ID_RE.fullmatch(track_id):
        raise ValueError(f"Invalid music track ID {track_id!r}")
    if backend not in MUSIC_BACKENDS:
        raise ValueError(f"Unsupported music backend {backend!r}; choose {', '.join(MUSIC_BACKENDS)}")
    load_dotenv(root / ".env")

    out_dir = music_dir(root)
    out_dir.mkdir(parents=True, exist_ok=True)
    dest_wav = out_dir / f"{track_id}.wav"
    if dest_wav.exists() and not overwrite:
        raise FileExistsError(f"Music track file already exists: {dest_wav}; pass --overwrite to replace")

    with tempfile.TemporaryDirectory(dir=out_dir) as tmp:
        staged = Path(tmp) / f"{track_id}.wav"
        if backend == "procedural":
            dur = synthesize_procedural_wav(staged, preset=preset, bpm=bpm, duration_s=duration_s)
            author = "Math_books procedural synthesizer"
            license_str = "CC0-1.0"
        elif backend == "musicgen":
            if not prompt.strip():
                raise ValueError("musicgen backend requires a non-empty --prompt")
            hf_token = os.getenv("HF-TOKEN") or os.getenv("HF_TOKEN")
            dur = synthesize_musicgen_wav(prompt, staged, hf_token=hf_token)
            author = "Meta facebook/MusicGen (Hugging Face Space)"
            license_str = "CC-BY-NC-4.0 (AI-generated instrumental)"
        elif backend == "ace_step":
            if not prompt.strip():
                raise ValueError("ace_step backend requires a non-empty --prompt")
            hf_token = os.getenv("HF-TOKEN") or os.getenv("HF_TOKEN")
            dur = synthesize_ace_step_wav(prompt, staged, duration_s=duration_s, hf_token=hf_token)
            author = "ACE-Step/ACE-Step (Hugging Face Space)"
            license_str = "Apache-2.0 (AI-generated instrumental)"
        else:
            if not prompt.strip():
                raise ValueError("lyria backend requires a non-empty --prompt")
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                raise RuntimeError("GEMINI_API_KEY is required for lyria music generation")
            dur = synthesize_lyria_wav(prompt, staged, api_key=api_key)
            author = "Google Lyria (Gemini API)"
            license_str = "Google AI Terms (AI-generated instrumental)"

        sha = hashlib.sha256(staged.read_bytes()).hexdigest()
        effective_title = title.strip() if isinstance(title, str) and title.strip() else f"{track_id} ({backend})"
        entry: dict[str, Any] = {
            "id": track_id,
            "file": dest_wav.name,
            "title": effective_title,
            "license": license_str,
            "author": author,
            "source": backend,
            "mood": mood,
            "bpm": int(round(bpm)),
            "duration_s": round(dur, 2),
            "tags": sorted(set(tags or [mood, backend])),
            **({"prompt": prompt} if prompt.strip() else {}),
            "sha256": sha,
        }
        return _register_track_entry(root, entry, staged_wav=staged, dest_wav=dest_wav, overwrite=overwrite)


def import_music_track(
    root: Path,
    source_file: Path,
    *,
    track_id: str,
    title: str,
    license_str: str,
    author: str,
    mood: str = "energetic",
    bpm: int | None = None,
    tags: list[str] | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Import an external royalty-free/CC0 audio file (MP3/WAV/OGG/FLAC) into the reusable music bank."""
    if not _ID_RE.fullmatch(track_id):
        raise ValueError(f"Invalid music track ID {track_id!r}")
    if not isinstance(title, str) or not title.strip():
        raise ValueError("Music track title must be a non-empty string")
    if not isinstance(license_str, str) or not license_str.strip():
        raise ValueError("Music track license must be a non-empty string")
    if not isinstance(author, str) or not author.strip():
        raise ValueError("Music track author must be a non-empty string")
    if not source_file.is_file():
        raise FileNotFoundError(f"Source audio file not found: {source_file}")
    out_dir = music_dir(root)
    out_dir.mkdir(parents=True, exist_ok=True)
    dest_wav = out_dir / f"{track_id}.wav"
    if dest_wav.exists() and not overwrite:
        raise FileExistsError(f"Music track file already exists: {dest_wav}; pass --overwrite to replace")
    with tempfile.TemporaryDirectory(dir=out_dir) as tmp:
        staged = Path(tmp) / f"{track_id}.wav"
        _normalize_to_wav(source_file, staged)
        dur = wav_duration(staged)
        sha = hashlib.sha256(staged.read_bytes()).hexdigest()
        entry: dict[str, Any] = {
            "id": track_id,
            "file": dest_wav.name,
            "title": title.strip(),
            "license": license_str.strip(),
            "author": author.strip(),
            "source": "imported",
            "mood": mood,
            **({"bpm": bpm} if bpm is not None else {}),
            "duration_s": round(dur, 2),
            "tags": sorted(set(tags or [mood, "imported"])),
            "sha256": sha,
        }
        return _register_track_entry(root, entry, staged_wav=staged, dest_wav=dest_wav, overwrite=overwrite)


def render_music_bed(track_path: Path, out_wav: Path, duration_s: float) -> float:
    """Loop/trim a licensed track to exact duration_s with smooth fade-in/fade-out as 24 kHz mono PCM16 WAV."""
    if duration_s <= 0:
        raise ValueError("Music duration must be positive")
    fade_in = min(0.5, duration_s * 0.2)
    fade_out = min(0.8, duration_s * 0.25)
    fade_out_start = max(0.0, duration_s - fade_out)
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-v",
        "error",
        "-stream_loop",
        "-1",
        "-i",
        str(track_path),
        "-t",
        f"{duration_s:.3f}",
        "-af",
        f"afade=t=in:st=0:d={fade_in:.3f},afade=t=out:st={fade_out_start:.3f}:d={fade_out:.3f}",
        "-ac",
        "1",
        "-ar",
        "24000",
        "-sample_fmt",
        "s16",
        "-f",
        "wav",
        str(out_wav),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=60)
    return wav_duration(out_wav)
