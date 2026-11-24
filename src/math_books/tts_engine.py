"""Shared Gemini TTS synthesis engine with rate-limit model rotation and manifest generation."""

from __future__ import annotations

import base64
import fcntl
import hashlib
import importlib
import json
import os
import re
import shutil
import tempfile
import time
import wave
from collections.abc import Sequence
from contextlib import contextmanager
from pathlib import Path

import httpx
from dotenv import load_dotenv

from math_books.content_review import require_content_review, script_digest
from math_books.uk_tts_providers import UkrainianFallbackTTS, build_ukrainian_providers
from math_books.voiceover_qa import RecognitionError, model_cache, verify_clip

PRIMARY_MODEL = "gemini-3.8-flash-tts"
SECONDARY_MODEL = "gemini-2.5-flash-preview-tts"
FALLBACK_MODEL = "gemini-3.8-flash-lite-tts"
PROMPT_REVISION = 2
SUPPORTED_PROMPT_REVISIONS = (PROMPT_REVISION, 1)
RETRYABLE_HTTP_STATUSES = {404, 408, 429, 500, 502, 503, 504}


class FatalTTSError(RuntimeError):
    """Non-retryable client or authentication error from Gemini TTS."""


def wav_duration(wav_path: Path) -> float:
    """Return duration of a WAV file in seconds."""
    with wave.open(str(wav_path), "rb") as wf:
        nframes = wf.getnframes()
        pcm = wf.readframes(nframes)
        if len(pcm) != nframes * wf.getnchannels() * wf.getsampwidth():
            raise ValueError(f"Truncated WAV PCM: {wav_path}")
        return nframes / float(wf.getframerate())


@contextmanager
def audio_lock(audio_dir: Path):
    """Fail clearly instead of racing TTS, rendering and verification for one topic."""
    audio_dir.mkdir(parents=True, exist_ok=True)
    with (audio_dir / ".pipeline.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError("This topic is busy with another TTS/build/verify operation") from error
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def request_fingerprint(
    text: str,
    voice: str,
    index: int,
    *,
    prompt_revision: int = PROMPT_REVISION,
    provider: str = "gemini",
) -> str:
    if provider != "gemini":
        request: dict[str, object] = {
            "text": text,
            "voice": voice,
            "provider": provider,
            "prompt_revision": prompt_revision,
        }
        return hashlib.sha256(json.dumps(request, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    model = PRIMARY_MODEL if index < 3 else SECONDARY_MODEL
    alt = SECONDARY_MODEL if model == PRIMARY_MODEL else FALLBACK_MODEL
    request = {"text": text, "voice": voice, "models": [model, alt], "prompt_revision": prompt_revision}
    return hashlib.sha256(json.dumps(request, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def valid_request_fingerprints(text: str, voice: str, index: int, *, provider: str = "gemini") -> set[str]:
    return {
        request_fingerprint(text, voice, index, prompt_revision=rev, provider=provider)
        for rev in SUPPORTED_PROMPT_REVISIONS
    }


def trim_wav_edges(path: Path, *, margin_s: float = 0.1) -> None:
    """Trim only leading/trailing low-amplitude PCM, preserving all internal pauses."""
    import numpy as np

    with wave.open(str(path), "rb") as wav:
        params = wav.getparams()
        pcm = wav.readframes(wav.getnframes())
    if params.sampwidth != 2:
        raise ValueError("Edge trimming requires 16-bit PCM")
    samples = np.frombuffer(pcm, dtype="<i2").astype(np.int32).reshape(-1, params.nchannels)
    audible = np.flatnonzero(np.max(np.abs(samples), axis=1) > 32768 * 10 ** (-40 / 20))
    if not len(audible):
        raise ValueError("Cannot trim entirely silent audio")
    margin = round(params.framerate * margin_s)
    start = max(0, int(audible[0]) - margin)
    end = min(len(samples), int(audible[-1]) + margin + 1)
    frame_bytes = params.nchannels * params.sampwidth
    with wave.open(str(path), "wb") as wav:
        wav.setparams(params)
        wav.writeframes(pcm[start * frame_bytes : end * frame_bytes])


def synthesize_gemini_tts(
    text: str,
    out_wav: Path,
    api_key: str,
    model: str = PRIMARY_MODEL,
    voice: str = "Puck",
) -> float:
    """Call Gemini TTS API and save WAV file, returning its duration in seconds."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": text}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}},
        },
    }
    resp = httpx.post(url, json=payload, timeout=60)
    if resp.status_code != 200:
        msg = f"Gemini TTS failed ({resp.status_code}): {resp.text[:400]}"
        if resp.status_code not in RETRYABLE_HTTP_STATUSES and 400 <= resp.status_code < 500:
            raise FatalTTSError(msg)
        raise RuntimeError(msg)

    data = resp.json()
    parts = data["candidates"][0]["content"]["parts"]
    audio_bytes = None
    mime_type = ""
    for p in parts:
        if "inlineData" in p:
            mime_type = p["inlineData"].get("mimeType", "")
            audio_bytes = base64.b64decode(p["inlineData"]["data"])
            break

    if audio_bytes is None:
        raise RuntimeError(f"No audio in response: {json.dumps(data, ensure_ascii=False)[:400]}")

    if "wav" in mime_type:
        out_wav.write_bytes(audio_bytes)
    else:
        # Raw L16 PCM at 24kHz mono
        with wave.open(str(out_wav), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(24000)
            wf.writeframes(audio_bytes)

    return wav_duration(out_wav)


def generate_topic_tts(
    scenes: Sequence[dict[str, str]],
    video_dir_name: str,
    *,
    force: bool = False,
    voice: str = "Puck",
    delay_s: float = 1.5,
    root: Path | None = None,
    trim_edges: bool = False,
    provider: str = "gemini",
    uk_profile: str | None = None,
) -> list[dict]:
    """Generate (or reuse) WAV files for all scenes of a topic and write manifest.json."""
    project_root = root or Path(__file__).resolve().parents[2]
    # Lazy import avoids a registry/engine import cycle while checking the real scene for known topics.
    from math_books.video_builder import VIDEO_TOPICS

    topic = next(
        (
            item
            for item in VIDEO_TOPICS.values()
            if item.video_dir == video_dir_name or Path(item.video_dir).name == Path(video_dir_name).name
        ),
        None,
    )
    if topic is not None and video_dir_name == Path(topic.video_dir).name:
        video_dir_name = topic.video_dir
    if topic is not None and script_digest(scenes) != script_digest(importlib.import_module(topic.tts_module).SCENES):
        raise ValueError("Caller script differs from the current registered narration")
    require_content_review(
        scenes, video_dir_name, project_root, expected_scene_file=topic.scene_file if topic else None
    )
    load_dotenv(project_root / ".env")
    api_key = os.getenv("GEMINI_API_KEY")

    audio_dir = project_root / video_dir_name / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    ids = [scene["id"] for scene in scenes]
    if not ids or len(set(ids)) != len(ids) or any(not re.fullmatch(r"[A-Za-z0-9_-]+", ident) for ident in ids):
        raise ValueError("Scene IDs must be nonempty, unique file-safe names")
    if provider not in ("gemini", "uk"):
        raise ValueError(f"Unsupported TTS provider '{provider}'. Choose 'gemini' or 'uk'.")
    # Immutable clip paths plus the final atomic manifest switch preserve previous batches.
    with audio_lock(audio_dir), tempfile.TemporaryDirectory(dir=audio_dir) as staging:
        return _generate_batch(
            scenes,
            audio_dir,
            Path(staging),
            api_key,
            force,
            voice,
            delay_s,
            trim_edges,
            project_root,
            provider=provider,
            uk_profile=uk_profile,
        )


def _check_clip_qa(
    wav_path: Path, text: str, scene_id: str, audio_dir: Path, project_root: Path, *, refresh: bool = False
) -> None:
    report = verify_clip(wav_path, text, audio_dir / "qa", model_cache(project_root), refresh=refresh)
    if not report["ok"]:
        issues = "; ".join(report.get("comparison", {}).get("issues", report.get("issues", ["bad speech"])))
        raise ValueError(f"Voiceover verification failed for {scene_id}: {issues}")


def _generate_batch(
    scenes,
    audio_dir,
    staging,
    api_key,
    force,
    voice,
    delay_s,
    trim_edges,
    project_root,
    *,
    provider: str = "gemini",
    uk_profile: str | None = None,
) -> list[dict]:
    meta: list[dict] = []
    uk_service: UkrainianFallbackTTS | None = None
    effective_voice = voice
    if provider == "uk":
        profile, uk_providers = build_ukrainian_providers(project_root, profile_id=uk_profile)
        uk_service = UkrainianFallbackTTS(uk_providers, profile_id=profile.profile_id)
        effective_voice = profile.profile_id

    for idx, scene in enumerate(scenes):
        wav_path = audio_dir / f"{scene['id']}.wav"
        cache_path = wav_path.with_suffix(".cache.json")
        model = PRIMARY_MODEL if idx < 3 else SECONDARY_MODEL
        alt = SECONDARY_MODEL if model == PRIMARY_MODEL else FALLBACK_MODEL
        fingerprint = request_fingerprint(scene["text"], effective_voice, idx, provider=provider)
        valid_fingerprints = valid_request_fingerprints(scene["text"], effective_voice, idx, provider=provider)
        try:
            cache = json.loads(cache_path.read_text(encoding="utf-8"))
            wav_path = audio_dir / cache.get("wav", wav_path.name)
            valid = (
                cache["fingerprint"] in valid_fingerprints
                and cache["wav_sha256"] == hashlib.sha256(wav_path.read_bytes()).hexdigest()
            )
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            cache, valid = {}, False
        if valid and not force:
            dur = wav_duration(wav_path)
            status = "cached"
            already_trimmed = bool(cache.get("trimmed"))
            if not (trim_edges and not already_trimmed):
                _check_clip_qa(wav_path, scene["text"], scene["id"], audio_dir, project_root)
        elif provider == "uk":
            assert uk_service is not None
            staged_wav = staging / f"{scene['id']}.wav"
            actual_provider_id, actual_voice = uk_service.synthesize(scene["text"], staged_wav)
            if trim_edges:
                trim_wav_edges(staged_wav)
            _check_clip_qa(staged_wav, scene["text"], scene["id"], audio_dir, project_root, refresh=True)
            dur = wav_duration(staged_wav)
            if dur <= 0:
                raise ValueError(f"Empty audio generated for {scene['id']}")
            cache = {
                "fingerprint": fingerprint,
                "provider": "uk",
                "model": actual_provider_id,
                "voice": effective_voice,
                "actual_voice": actual_voice,
                "wav_sha256": hashlib.sha256(staged_wav.read_bytes()).hexdigest(),
                **({"trimmed": True} if trim_edges else {}),
            }
            status = "generated"
            already_trimmed = trim_edges
        else:
            if not api_key:
                raise RuntimeError(f"GEMINI_API_KEY is required to generate uncached audio: {scene['id']}")
            staged_wav = staging / f"{scene['id']}.wav"
            candidate_models = [model, alt]
            for extra in (FALLBACK_MODEL, PRIMARY_MODEL, SECONDARY_MODEL):
                if extra not in candidate_models:
                    candidate_models.append(extra)
            actual_model = model
            last_error: Exception | None = None
            for attempt_idx, candidate in enumerate(candidate_models[:3]):
                if attempt_idx > 0 and delay_s > 0:
                    time.sleep(min(delay_s, 1.0))
                try:
                    actual_model = candidate
                    synthesize_gemini_tts(scene["text"], staged_wav, api_key, model=candidate, voice=voice)
                    if trim_edges:
                        trim_wav_edges(staged_wav)
                    _check_clip_qa(staged_wav, scene["text"], scene["id"], audio_dir, project_root, refresh=True)
                    last_error = None
                    break
                except (RecognitionError, FatalTTSError):
                    raise
                except (RuntimeError, ValueError, httpx.HTTPError) as error:
                    last_error = error
                    if isinstance(error, ValueError) and attempt_idx >= 1:
                        break
            if last_error is not None:
                raise last_error
            dur = wav_duration(staged_wav)
            if dur <= 0:
                raise ValueError(f"Empty audio generated for {scene['id']}")
            cache = {
                "fingerprint": fingerprint,
                "model": actual_model,
                "voice": voice,
                "wav_sha256": hashlib.sha256(staged_wav.read_bytes()).hexdigest(),
                **({"trimmed": True} if trim_edges else {}),
            }
            status = "generated"
            already_trimmed = trim_edges
            if idx < len(scenes) - 1 and delay_s > 0:
                time.sleep(delay_s)

        if (trim_edges and not already_trimmed) or status == "generated":
            staged_wav = staging / f"{scene['id']}.wav"
            if status == "cached":
                shutil.copy2(wav_path, staged_wav)
                if trim_edges:
                    trim_wav_edges(staged_wav)
                    cache["trimmed"] = True
                _check_clip_qa(staged_wav, scene["text"], scene["id"], audio_dir, project_root)
            dur = wav_duration(staged_wav)
            checksum = hashlib.sha256(staged_wav.read_bytes()).hexdigest()
            clip_fp = str(cache.get("fingerprint", fingerprint))
            wav_path = audio_dir / "clips" / f"{scene['id']}-{clip_fp[:12]}-{checksum[:12]}.wav"
            wav_path.parent.mkdir(exist_ok=True)
            cache.update(wav=str(wav_path.relative_to(audio_dir)), wav_sha256=checksum)
            staged_cache = staging / cache_path.name
            staged_cache.write_text(json.dumps(cache, indent=2), encoding="utf-8")
            staged_wav.replace(wav_path)
            staged_cache.replace(cache_path)

        print(f"[{scene['id']}] ({status}) -> {wav_path.name} ({dur:.2f}s)")
        meta.append({**scene, **cache, "wav": str(wav_path.relative_to(audio_dir)), "duration": dur})

    staged_manifest = staging / "manifest.json"
    staged_manifest.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    staged_manifest.replace(audio_dir / "manifest.json")
    print(f"Total audio duration: {sum(m['duration'] for m in meta):.2f}s")
    return meta
