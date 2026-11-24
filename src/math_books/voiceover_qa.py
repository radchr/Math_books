"""Local ASR gate with byte-, script- and policy-bound audit receipts."""

from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
import tempfile
from datetime import UTC, datetime
from functools import lru_cache
from importlib.metadata import version
from pathlib import Path

from math_books.spoken_text import compare_transcript

QA_POLICY_VERSION = 1
ASR_MODEL = "base"


class RecognitionError(RuntimeError):
    """The recognizer failed; this is not evidence of incorrect synthesized speech."""


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def policy_profile() -> dict:
    packages = ("faster-whisper", "pymorphy3", "num2words", "snowballstemmer")
    return {
        "revision": QA_POLICY_VERSION,
        "engine": "faster-whisper",
        "model": ASR_MODEL,
        "language": "ru",
        "beam_size": 5,
        "compute_type": "int8",
        "sample_rate": 16000,
        "packages": {name: version(name) for name in packages},
        "verifier_sha256": _sha(Path(__file__).read_bytes()),
        "normalizer_sha256": _sha(Path(__file__).with_name("spoken_text.py").read_bytes()),
    }


def policy_fingerprint() -> str:
    return _sha(json.dumps(policy_profile(), sort_keys=True).encode())


def model_cache(root: Path) -> Path:
    return Path(os.environ.get("MATH_BOOKS_ASR_CACHE", str(root / ".cache/whisper"))).resolve()


@lru_cache(maxsize=2)
def _recognizer(cache_dir: str):
    from faster_whisper import WhisperModel

    return WhisperModel(ASR_MODEL, device="cpu", compute_type="int8", cpu_threads=8, download_root=cache_dir)


def transcribe_audio(wav_path: Path, cache_dir: Path) -> list[dict]:
    """Decode through ffmpeg, avoiding dependency-specific PyAV decoding behavior."""
    import numpy as np

    try:
        decoded = subprocess.run(
            ["ffmpeg", "-v", "error", "-i", str(wav_path), "-f", "f32le", "-ac", "1", "-ar", "16000", "pipe:1"],
            check=True,
            capture_output=True,
            timeout=60,
        )
        samples = np.frombuffer(decoded.stdout, dtype=np.float32)
        segments, _ = _recognizer(str(cache_dir)).transcribe(
            samples, language="ru", beam_size=5, condition_on_previous_text=False, word_timestamps=True
        )
        return [
            {
                "start": float(segment.start),
                "end": float(segment.end),
                "text": segment.text,
                "words": [
                    {"start": float(word.start), "end": float(word.end), "word": word.word}
                    for word in segment.words or []
                ],
            }
            for segment in segments
        ]
    except Exception as error:
        # Do not echo network URLs/credentials from backend exceptions into CLI logs.
        raise RecognitionError(
            f"Local ASR unavailable ({type(error).__name__}). Check ffmpeg, uv sync and model cache/network access."
        ) from None


def _transcript(segments: object) -> str:
    if not isinstance(segments, list):
        raise ValueError("ASR segments must be a list")
    texts = []
    previous = 0.0
    for segment in segments:
        if (
            not isinstance(segment, dict)
            or not isinstance(segment.get("text"), str)
            or type(segment.get("start")) not in (float, int)
            or type(segment.get("end")) not in (float, int)
            or not math.isfinite(segment["start"])
            or not math.isfinite(segment["end"])
            or segment["start"] < previous
            or segment["end"] < segment["start"]
        ):
            raise ValueError("Malformed or nonmonotonic ASR segments")
        previous = segment["start"]
        texts.append(segment["text"].strip())
    return " ".join(texts)


def _unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate QA receipt key")
        result[key] = value
    return result


def verify_clip(wav_path: Path, expected_text: str, qa_dir: Path, cache_dir: Path, *, refresh=False) -> dict:
    """Recompute text comparison on cached evidence; never trust its saved ok flag."""
    # Imported lazily to avoid a synthesis/verification import cycle.
    from math_books.tts_engine import wav_duration

    if wav_duration(wav_path) <= 0:
        raise ValueError(f"Empty narration WAV: {wav_path}")
    audio_hash = _sha(wav_path.read_bytes())
    text_hash = _sha(expected_text.encode())
    policy_hash = policy_fingerprint()
    identity = {"wav_sha256": audio_hash, "text_sha256": text_hash, "policy_sha256": policy_hash}
    path = qa_dir / f"{audio_hash}-{text_hash[:16]}-{policy_hash[:16]}.json"
    if not refresh:
        try:
            cached = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_keys)
            if (
                not isinstance(cached, dict)
                or any(cached.get(key) != value for key, value in identity.items())
                or cached.get("expected_text") != expected_text
                or cached.get("profile") != policy_profile()
                or cached.get("transcript") != _transcript(cached.get("segments"))
            ):
                raise ValueError("Stale QA receipt")
            comparison = compare_transcript(expected_text, cached["transcript"])
            return {
                **cached,
                "comparison": comparison,
                "ok": comparison["ok"],
                "cached": True,
                "receipt_path": str(path),
            }
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            pass
    segments = transcribe_audio(wav_path, cache_dir)
    try:
        transcript = _transcript(segments)
    except ValueError as error:
        raise RecognitionError(str(error)) from None
    if _sha(wav_path.read_bytes()) != audio_hash:
        raise RecognitionError("WAV changed during recognition; no approval was recorded")
    comparison = compare_transcript(expected_text, transcript)
    report = {
        **identity,
        "profile": policy_profile(),
        "expected_text": expected_text,
        "transcript": transcript,
        "segments": segments,
        "comparison": comparison,
        "ok": comparison["ok"],
        "checked_at": datetime.now(UTC).isoformat(),
    }
    qa_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", dir=qa_dir, encoding="utf-8", delete=False) as output:
        temporary = Path(output.name)
        json.dump(report, output, ensure_ascii=False, indent=2)
        output.write("\n")
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return {**report, "cached": False, "receipt_path": str(path)}


def verify_manifest(manifest_path: Path, manifest: list[dict], root: Path, *, refresh=False) -> dict:
    clips = []
    for item in manifest:
        try:
            report = verify_clip(
                manifest_path.parent / item["wav"],
                item["text"],
                manifest_path.parent / "qa",
                model_cache(root),
                refresh=refresh,
            )
            clips.append({"id": item["id"], **report})
        except (RecognitionError, OSError, ValueError) as error:
            clips.append(
                {
                    "id": item["id"],
                    "ok": False,
                    "issues": [str(error)],
                    "backend_error": isinstance(error, RecognitionError),
                }
            )
            if isinstance(error, RecognitionError):
                break
    issues = [
        f"{clip['id']}: " + "; ".join(clip.get("comparison", {}).get("issues", clip.get("issues", [])))
        for clip in clips
        if not clip["ok"]
    ]
    if not manifest:
        issues.append("Empty audio manifest")
    return {"ok": not issues, "issues": issues, "clips": clips}


def require_manifest_quality(manifest_path: Path, manifest: list[dict], root: Path) -> dict:
    report = verify_manifest(manifest_path, manifest, root)
    if not report["ok"]:
        raise ValueError("Voiceover verification blocked production: " + "; ".join(report["issues"]))
    return report
