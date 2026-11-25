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

from math_books.languages import validate_language
from math_books.media_io import wav_duration
from math_books.pipeline_errors import RecognitionError as RecognitionError
from math_books.pipeline_errors import ReviewRequiredError as ReviewRequiredError
from math_books.spoken_text import compare_transcript

QA_POLICY_VERSION = 1
ASR_MODEL = "base"
ASR_MODELS = frozenset({"tiny", "base", "small", "medium", "large-v3", "tiny.en", "base.en", "small.en", "medium.en"})


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def analyze_audio(path: Path) -> dict:
    """Load the acoustic analyzer only for explicitly enabled modern QA."""
    from math_books.audio_quality import analyze_audio as analyze

    return analyze(path)


def _quality_result(wav_path: Path, comparison: dict, quality_check: bool) -> dict:
    if not quality_check:
        return {"ok": comparison["ok"]}
    acoustic = analyze_audio(wav_path)
    if acoustic.get("status") == "fail":
        status, reason = "fail", "Acoustic defect: " + "; ".join(acoustic.get("issues", []))
    elif not acoustic.get("ok") or acoustic.get("status") != "pass":
        status, reason = (
            "needs_review",
            "Acoustic evidence requires review: "
            + "; ".join(acoustic.get("issues", []) + acoustic.get("warnings", [])),
        )
    elif not comparison["ok"]:
        status, reason = "needs_review", "ASR text mismatch requires review: " + "; ".join(comparison.get("issues", []))
    else:
        status, reason = "pass", "Text and acoustic checks passed"
    return {"ok": status == "pass", "status": status, "reason": reason, "acoustics": acoustic, "quality_check": True}


def _finite_diagnostics(source: object, names: tuple[str, ...]) -> dict:
    return {
        name: value
        for name in names
        if isinstance(value := getattr(source, name, None), (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    }


def asr_model(language: str) -> str:
    """Resolve an explicit local multilingual model without permitting paths or URLs."""
    language = validate_language(language)
    default = "small" if language == "uk" else ASR_MODEL
    selected = os.environ.get(
        f"MATH_BOOKS_ASR_MODEL_{language.upper()}", os.environ.get("MATH_BOOKS_ASR_MODEL", default)
    )
    if selected not in ASR_MODELS or (language != "en" and selected.endswith(".en")):
        raise ValueError(f"Unsupported ASR model for {language}; use a supported Whisper model ID")
    return selected


def policy_profile(*, language="ru") -> dict:
    from math_books.audio_quality import policy_profile as acoustic_profile

    language = validate_language(language)
    packages = ("faster-whisper", "pymorphy3", "num2words", "snowballstemmer")
    return {
        "revision": QA_POLICY_VERSION,
        "engine": "faster-whisper",
        "model": asr_model(language),
        "language": language,
        "beam_size": 5,
        "compute_type": "int8",
        "sample_rate": 16000,
        "packages": {name: version(name) for name in packages},
        "verifier_sha256": _sha(Path(__file__).read_bytes()),
        "normalizer_sha256": _sha(Path(__file__).with_name("spoken_text.py").read_bytes()),
        "numeric_normalizer_sha256": _sha(Path(__file__).with_name("multilingual_numbers.py").read_bytes()),
        "acoustic_policy_sha256": _sha(Path(__file__).with_name("audio_quality.py").read_bytes()),
        "acoustic_policy": acoustic_profile(),
    }


def policy_fingerprint(*, language="ru") -> str:
    language = validate_language(language)
    profile = policy_profile() if language == "ru" else policy_profile(language=language)
    return _sha(json.dumps(profile, sort_keys=True).encode())


def model_cache(root: Path) -> Path:
    return Path(os.environ.get("MATH_BOOKS_ASR_CACHE", str(root / ".cache/whisper"))).resolve()


@lru_cache(maxsize=4)
def _recognizer(cache_dir: str, model_name: str = ASR_MODEL):
    from faster_whisper import WhisperModel

    return WhisperModel(model_name, device="cpu", compute_type="int8", cpu_threads=8, download_root=cache_dir)


def transcribe_audio(wav_path: Path, cache_dir: Path, *, language="ru") -> list[dict]:
    """Decode through ffmpeg, avoiding dependency-specific PyAV decoding behavior."""
    language = validate_language(language)
    selected_model = asr_model(language)
    import numpy as np

    try:
        decoded = subprocess.run(
            ["ffmpeg", "-v", "error", "-i", str(wav_path), "-f", "f32le", "-ac", "1", "-ar", "16000", "pipe:1"],
            check=True,
            capture_output=True,
            timeout=60,
        )
        samples = np.frombuffer(decoded.stdout, dtype=np.float32)
        recognizer = (
            _recognizer(str(cache_dir))
            if selected_model == ASR_MODEL
            else _recognizer(str(cache_dir), model_name=selected_model)
        )
        segments, _ = recognizer.transcribe(
            samples, language=language, beam_size=5, condition_on_previous_text=False, word_timestamps=True
        )
        return [
            {
                "start": float(segment.start),
                "end": float(segment.end),
                "text": segment.text,
                **_finite_diagnostics(segment, ("avg_logprob", "no_speech_prob")),
                "words": [
                    {
                        "start": float(word.start),
                        "end": float(word.end),
                        "word": word.word,
                        **_finite_diagnostics(word, ("probability",)),
                    }
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


def verify_clip(
    wav_path: Path,
    expected_text: str,
    qa_dir: Path,
    cache_dir: Path,
    *,
    refresh=False,
    language="ru",
    quality_check=False,
) -> dict:
    """Recompute text comparison on cached evidence; never trust its saved ok flag."""
    language = validate_language(language)
    if wav_duration(wav_path) <= 0:
        raise ValueError(f"Empty narration WAV: {wav_path}")
    audio_hash = _sha(wav_path.read_bytes())
    text_hash = _sha(expected_text.encode())
    policy_hash = policy_fingerprint() if language == "ru" else policy_fingerprint(language=language)
    profile = policy_profile() if language == "ru" else policy_profile(language=language)
    identity = {"wav_sha256": audio_hash, "text_sha256": text_hash, "policy_sha256": policy_hash, "language": language}
    path = qa_dir / f"{audio_hash}-{text_hash[:16]}-{policy_hash[:16]}.json"
    if not refresh:
        try:
            cached = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_keys)
            if (
                not isinstance(cached, dict)
                or any(cached.get(key) != value for key, value in identity.items())
                or cached.get("expected_text") != expected_text
                or cached.get("profile") != profile
                or cached.get("transcript") != _transcript(cached.get("segments"))
            ):
                raise ValueError("Stale QA receipt")
            comparison = compare_transcript(expected_text, cached["transcript"], language=language)
            return {
                **cached,
                "comparison": comparison,
                **_quality_result(wav_path, comparison, quality_check),
                "cached": True,
                "receipt_path": str(path),
            }
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            pass
    segments = (
        transcribe_audio(wav_path, cache_dir)
        if language == "ru"
        else transcribe_audio(wav_path, cache_dir, language=language)
    )
    try:
        transcript = _transcript(segments)
    except ValueError as error:
        raise RecognitionError(str(error)) from None
    if _sha(wav_path.read_bytes()) != audio_hash:
        raise RecognitionError("WAV changed during recognition; no approval was recorded")
    comparison = compare_transcript(expected_text, transcript, language=language)
    report = {
        **identity,
        "profile": profile,
        "expected_text": expected_text,
        "transcript": transcript,
        "segments": segments,
        "comparison": comparison,
        **_quality_result(wav_path, comparison, quality_check),
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
    try:
        languages = {validate_language(item.get("language", "ru")) for item in manifest}
        if len(languages) > 1:
            raise ValueError("Mixed narration languages in audio manifest")
    except ValueError as error:
        return {"ok": False, "issues": [str(error)], "clips": []}
    clips: list[dict] = []
    for item in manifest:
        try:
            language_options = {} if item.get("language", "ru") == "ru" else {"language": item["language"]}
            if item.get("quality_check", False):
                language_options["quality_check"] = True
            report = verify_clip(
                manifest_path.parent / item["wav"],
                item["text"],
                manifest_path.parent / "qa",
                model_cache(root),
                refresh=refresh,
                **language_options,
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
        f"{clip['id']}: "
        + str(clip.get("reason") or "; ".join(clip.get("comparison", {}).get("issues", clip.get("issues", []))))
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


def timing_snapshot(manifest_path: Path, manifest: list[dict], root: Path) -> dict[str, list[dict]]:
    """Read current approved word evidence without recognition, refresh, or writes."""
    languages = {validate_language(item.get("language", "ru")) for item in manifest}
    if len(languages) != 1:
        raise ValueError("Timing snapshot requires a nonempty, single-language manifest")
    language = next(iter(languages))
    profile = policy_profile() if language == "ru" else policy_profile(language=language)
    policy_hash = policy_fingerprint() if language == "ru" else policy_fingerprint(language=language)
    snapshot = {}
    for item in manifest:
        if item["id"] in snapshot:
            raise ValueError("Duplicate scene ID in timing snapshot")
        wav_path = manifest_path.parent / item["wav"]
        audio_hash = _sha(wav_path.read_bytes())
        text_hash = _sha(item["text"].encode())
        path = manifest_path.parent / "qa" / f"{audio_hash}-{text_hash[:16]}-{policy_hash[:16]}.json"
        identity = {
            "wav_sha256": audio_hash,
            "text_sha256": text_hash,
            "policy_sha256": policy_hash,
            "language": language,
        }
        try:
            receipt = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_keys)
            if (
                not isinstance(receipt, dict)
                or any(receipt.get(key) != value for key, value in identity.items())
                or receipt.get("expected_text") != item["text"]
                or receipt.get("profile") != profile
                or receipt.get("transcript") != _transcript(receipt.get("segments"))
                or not compare_transcript(item["text"], receipt["transcript"], language=language)["ok"]
            ):
                raise ValueError("Stale or failed QA receipt")
            if item.get("quality_check", False):
                quality = _quality_result(wav_path, {"ok": True}, True)
                if not quality["ok"]:
                    raise ValueError(quality["reason"])
            duration = wav_duration(wav_path)
            words = []
            previous = 0.0
            for segment in receipt["segments"]:
                if not isinstance(segment.get("words"), list):
                    raise ValueError("Missing word timestamps")
                for word in segment["words"]:
                    if (
                        not isinstance(word, dict)
                        or not isinstance(word.get("word"), str)
                        or not word["word"].strip()
                        or type(word.get("start")) not in (int, float)
                        or type(word.get("end")) not in (int, float)
                        or not math.isfinite(word["start"])
                        or not math.isfinite(word["end"])
                        or word["start"] < previous
                        or word["end"] < word["start"]
                        or word["end"] > duration
                    ):
                        raise ValueError("Invalid word timestamps")
                    previous = word["start"]
                    words.append({"start": word["start"], "end": word["end"], "word": word["word"]})
            if not words or _sha(wav_path.read_bytes()) != audio_hash:
                raise ValueError("Missing word timestamps or WAV changed during snapshot")
            snapshot[item["id"]] = words
        except (OSError, KeyError, TypeError, AttributeError, ValueError) as error:
            raise ValueError(f"Timing snapshot unavailable for {item['id']}: {error}") from None
    return snapshot
