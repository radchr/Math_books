"""Shared Gemini TTS synthesis engine with rate-limit model rotation and manifest generation."""

from __future__ import annotations

import base64
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
from pathlib import Path
from urllib.parse import quote, quote_plus

import httpx
from dotenv import load_dotenv

from math_books.content_review import require_content_review, script_digest
from math_books.languages import validate_language
from math_books.media_io import audio_lock as audio_lock
from math_books.media_io import wav_duration as wav_duration
from math_books.pipeline_errors import FatalTTSError as FatalTTSError
from math_books.uk_tts_providers import (
    UkrainianFallbackTTS,
    build_ukrainian_providers,
    profile_fingerprint,
    timing_sidecar,
    validate_provider_timings,
)
from math_books.voiceover_qa import RecognitionError, ReviewRequiredError, model_cache, verify_clip

PRIMARY_MODEL = "gemini-3.8-flash-tts"
SECONDARY_MODEL = "gemini-2.5-flash-preview-tts"
FALLBACK_MODEL = "gemini-3.8-flash-lite-tts"
PROMPT_REVISION = 2
SUPPORTED_PROMPT_REVISIONS = (PROMPT_REVISION, 1)
RETRYABLE_HTTP_STATUSES = {404, 408, 429, 500, 502, 503, 504}


def _redact_secret(message: str, api_key: str) -> str:
    if api_key:
        for value in {api_key, quote(api_key, safe=""), quote_plus(api_key)}:
            message = message.replace(value, "[REDACTED]")
    return message


def _safe_gemini_error(error: Exception, api_key: str) -> Exception:
    """Keep retry classification while removing credentials from surfaced errors."""
    message = _redact_secret(str(error), api_key)
    if message == str(error):
        return error
    if isinstance(error, httpx.HTTPStatusError):
        request = httpx.Request(error.request.method, _redact_secret(str(error.request.url), api_key))
        return httpx.HTTPStatusError(message, request=request, response=httpx.Response(error.response.status_code))
    if isinstance(error, (httpx.RequestError, RuntimeError, ValueError)):
        return type(error)(message)
    return RuntimeError(message)


def request_fingerprint(
    text: str,
    voice: str,
    index: int,
    *,
    prompt_revision: int = PROMPT_REVISION,
    provider: str = "gemini",
    language: str = "ru",
    provider_config: str | None = None,
    pin_model: bool = False,
) -> str:
    language = validate_language(language)
    if provider != "gemini":
        request: dict[str, object] = {
            "text": text,
            "voice": voice,
            "provider": provider,
            "prompt_revision": prompt_revision,
        }
    else:
        model = PRIMARY_MODEL if pin_model or language != "ru" or index < 3 else SECONDARY_MODEL
        alt = SECONDARY_MODEL if model == PRIMARY_MODEL else FALLBACK_MODEL
        request = {"text": text, "voice": voice, "models": [model, alt], "prompt_revision": prompt_revision}
    if language != "ru":
        request["language"] = language
    if provider_config is not None:
        request["provider_config"] = provider_config
    if pin_model:
        request["pin_model"] = True
    return hashlib.sha256(json.dumps(request, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def valid_request_fingerprints(
    text: str,
    voice: str,
    index: int,
    *,
    provider: str = "gemini",
    language: str = "ru",
    provider_config: str | None = None,
    pin_model: bool = False,
) -> set[str]:
    return {
        request_fingerprint(
            text,
            voice,
            index,
            prompt_revision=rev,
            provider=provider,
            language=language,
            provider_config=provider_config,
            pin_model=pin_model,
        )
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
    evidence_path = timing_sidecar(path)
    if evidence_path.is_file():
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        evidence["trim_start_samples"] += start
        evidence["wav_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        evidence_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")


def synthesize_gemini_tts(
    text: str,
    out_wav: Path,
    api_key: str,
    model: str = PRIMARY_MODEL,
    voice: str = "Puck",
) -> float:
    """Call Gemini TTS API and save WAV file, returning its duration in seconds."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    payload = {
        "contents": [{"parts": [{"text": text}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}},
        },
    }
    try:
        resp = httpx.post(url, headers={"x-goog-api-key": api_key}, json=payload, timeout=60)
    except httpx.HTTPError as error:
        raise _safe_gemini_error(error, api_key) from None
    if resp.status_code != 200:
        msg = f"Gemini TTS failed ({resp.status_code}): {_redact_secret(resp.text, api_key)[:400]}"
        if resp.status_code not in RETRYABLE_HTTP_STATUSES and 400 <= resp.status_code < 500:
            raise FatalTTSError(msg)
        raise RuntimeError(msg)

    data = resp.json()
    candidates = data.get("candidates") if isinstance(data, dict) else None
    first_candidate = candidates[0] if isinstance(candidates, list) and candidates else None
    content = first_candidate.get("content") if isinstance(first_candidate, dict) else None
    parts = content.get("parts") if isinstance(content, dict) else None
    audio_bytes = None
    mime_type = ""
    if isinstance(parts, list):
        for p in parts:
            if isinstance(p, dict) and isinstance(p.get("inlineData"), dict) and "data" in p["inlineData"]:
                mime_type = str(p["inlineData"].get("mimeType", ""))
                audio_bytes = base64.b64decode(p["inlineData"]["data"])
                break

    if audio_bytes is None:
        detail = _redact_secret(json.dumps(data, ensure_ascii=False), api_key)[:400]
        raise RuntimeError(f"No audio in response: {detail}")

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
    language: str | None = None,
    pin_model: bool = False,
    fallback_to_uk: bool = False,
) -> list[dict]:
    """Generate (or reuse) WAV files for all scenes of a topic and write manifest.json."""
    project_root = root or Path(__file__).resolve().parents[2]
    language = validate_language(language if language is not None else ("uk" if provider == "uk" else "ru"))
    if provider == "uk" and language != "uk":
        raise ValueError("The uk TTS provider requires language='uk'")
    from math_books.lessons import lesson_path
    from math_books.topics import VIDEO_TOPICS, get_topic, topic_scenes

    topic = next(
        (
            item
            for item in VIDEO_TOPICS.values()
            if item.video_dir == video_dir_name or Path(item.video_dir).name == Path(video_dir_name).name
        ),
        None,
    )
    directory = Path(video_dir_name)
    candidate = directory.parent.name if directory.name in ("uk", "ru", "en") else directory.name
    candidate = candidate.removeprefix("video_")
    if topic is None and re.fullmatch(r"[a-z][a-z0-9_]*", candidate) and lesson_path(project_root, candidate).is_file():
        topic = get_topic(candidate, language, project_root)
        if directory.as_posix() != topic.video_dir:
            raise ValueError(f"Future lesson output path must be {topic.video_dir}")
        if script_digest(scenes) != script_digest(topic_scenes(topic, project_root)):
            raise ValueError("Caller script differs from localized lesson content")
        pin_model = True
    if topic is not None and video_dir_name == Path(topic.video_dir).name:
        video_dir_name = topic.video_dir
    if (
        topic is not None
        and topic.lesson_file is None
        and script_digest(scenes) != script_digest(importlib.import_module(topic.tts_module).SCENES)
    ):
        raise ValueError("Caller script differs from the current registered narration")
    require_content_review(
        scenes,
        video_dir_name,
        project_root,
        expected_scene_file=topic.scene_file if topic else None,
        **({"language": language} if language != "ru" else {}),
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
        try:
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
                language=language,
                pin_model=pin_model,
            )
        except (RecognitionError, ReviewRequiredError, ValueError):
            raise
        except (FatalTTSError, RuntimeError, httpx.HTTPError) as error:
            if not (fallback_to_uk and provider == "gemini" and language == "uk"):
                raise
            print(f"Gemini TTS unavailable ({error}); falling back to Ukrainian TTS chain.")
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
                provider="uk",
                uk_profile=uk_profile,
                language=language,
                pin_model=pin_model,
            )


def _write_immutable_evidence(path: Path, data: bytes) -> None:
    """Create evidence once; a collision must contain exactly the same bytes."""
    try:
        with path.open("xb") as output:
            output.write(data)
    except FileExistsError:
        if path.read_bytes() != data:
            raise ReviewRequiredError(f"Review evidence collision; existing file was not overwritten: {path}") from None


def _retain_review_required(
    wav_path: Path, text: str, report: dict, audio_dir: Path, language: str
) -> tuple[Path, Path]:
    """Retain unapproved speech and its full diagnostic report outside production clips."""
    pcm = wav_path.read_bytes()
    audio_hash = hashlib.sha256(pcm).hexdigest()
    text_hash = hashlib.sha256(text.encode()).hexdigest()
    report_bytes = json.dumps(report, sort_keys=True, ensure_ascii=False).encode()
    report_hash = hashlib.sha256(report_bytes).hexdigest()
    policy_hash = report.get("policy_sha256")
    if not isinstance(policy_hash, str) or not re.fullmatch(r"[a-f0-9]{64}", policy_hash):
        policy_hash = report_hash
    directory = audio_dir / "review_required"
    directory.mkdir(exist_ok=True)
    stem = f"{audio_hash}-{text_hash[:16]}-{policy_hash[:16]}"
    retained_wav = directory / f"{stem}.wav"
    retained_report = directory / f"{stem}-{report_hash[:16]}.json"
    evidence = {
        "evidence_only": True,
        "purpose": "Unapproved voiceover retained for manual review; never a production approval",
        "language": language,
        "wav": str(retained_wav),
        "wav_sha256": audio_hash,
        "text_sha256": text_hash,
        "source_report": report,
    }
    _write_immutable_evidence(retained_wav, pcm)
    _write_immutable_evidence(
        retained_report, json.dumps(evidence, sort_keys=True, ensure_ascii=False, indent=2).encode()
    )
    return retained_wav, retained_report


def _check_clip_qa(
    wav_path: Path,
    text: str,
    scene_id: str,
    audio_dir: Path,
    project_root: Path,
    *,
    refresh: bool = False,
    language: str = "ru",
    quality_check: bool = False,
) -> None:
    report = verify_clip(
        wav_path,
        text,
        audio_dir / "qa",
        model_cache(project_root),
        refresh=refresh,
        **({"language": language} if language != "ru" else {}),
        **({"quality_check": True} if quality_check else {}),
    )
    if report.get("status") == "needs_review":
        try:
            retained_wav, retained_report = _retain_review_required(wav_path, text, report, audio_dir, language)
        except (OSError, TypeError, ValueError) as error:
            raise ReviewRequiredError(
                f"Voiceover needs review for {scene_id}; unable to retain evidence in "
                f"{audio_dir / 'review_required'}: {error}"
            ) from error
        raise ReviewRequiredError(
            f"Voiceover needs review for {scene_id}; retained WAV: {retained_wav}; evidence report: {retained_report}"
        )
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
    language: str = "ru",
    pin_model: bool = False,
) -> list[dict]:
    meta: list[dict] = []
    uk_service: UkrainianFallbackTTS | None = None
    effective_voice = voice
    config_fingerprint = None
    pinned_gemini_model: str | None = None
    if provider == "uk":
        profile, uk_providers = build_ukrainian_providers(project_root, profile_id=uk_profile)
        uk_service = UkrainianFallbackTTS(uk_providers, profile_id=profile.profile_id)
        effective_voice = profile.profile_id
        config_fingerprint = profile_fingerprint(profile, uk_providers)

    def fingerprints(scene, idx):
        return (
            request_fingerprint(
                scene["text"],
                effective_voice,
                idx,
                provider=provider,
                language=language,
                provider_config=config_fingerprint,
                pin_model=pin_model,
            ),
            valid_request_fingerprints(
                scene["text"],
                effective_voice,
                idx,
                provider=provider,
                language=language,
                provider_config=config_fingerprint,
                pin_model=pin_model,
            ),
        )

    # Inspect every reusable clip first: a missing early scene must respect a later cached voice.
    if (uk_service is not None or language != "ru" or pin_model) and not force:
        for idx, scene in enumerate(scenes):
            try:
                cache = json.loads((audio_dir / f"{scene['id']}.cache.json").read_text(encoding="utf-8"))
                cached_wav = (audio_dir / cache["wav"]).resolve()
                if not cached_wav.is_relative_to(audio_dir.resolve()):
                    continue
                reusable = (
                    cache["fingerprint"] in fingerprints(scene, idx)[1]
                    and cache["wav_sha256"] == hashlib.sha256(cached_wav.read_bytes()).hexdigest()
                )
                identity = (cache["model"], cache.get("actual_voice", cache["voice"]))
                if reusable:
                    validate_provider_timings(cache, audio_dir)
            except (OSError, ValueError, KeyError, TypeError, AttributeError):
                continue
            if reusable:
                if uk_service is not None:
                    uk_service.pin(*identity)
                else:
                    if pinned_gemini_model is not None and pinned_gemini_model != identity[0]:
                        raise ValueError("Cached Gemini clips mix model identities")
                    if identity[1] != voice:
                        raise ValueError("Cached Gemini voice differs from requested voice")
                    pinned_gemini_model = identity[0]

    for idx, scene in enumerate(scenes):
        wav_path = audio_dir / f"{scene['id']}.wav"
        cache_path = wav_path.with_suffix(".cache.json")
        model = PRIMARY_MODEL if pin_model or language != "ru" or idx < 3 else SECONDARY_MODEL
        alt = SECONDARY_MODEL if model == PRIMARY_MODEL else FALLBACK_MODEL
        fingerprint, valid_fingerprints = fingerprints(scene, idx)
        try:
            cache = json.loads(cache_path.read_text(encoding="utf-8"))
            wav_path = (audio_dir / cache.get("wav", wav_path.name)).resolve()
            if not wav_path.is_relative_to(audio_dir.resolve()):
                raise ValueError("Cached WAV path escapes audio directory")
            valid = (
                cache["fingerprint"] in valid_fingerprints
                and cache["wav_sha256"] == hashlib.sha256(wav_path.read_bytes()).hexdigest()
            )
            if valid:
                validate_provider_timings(cache, audio_dir)
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            cache, valid = {}, False
        if valid and not force:
            dur = wav_duration(wav_path)
            status = "cached"
            already_trimmed = bool(cache.get("trimmed"))
            if not (trim_edges and not already_trimmed):
                _check_clip_qa(
                    wav_path,
                    scene["text"],
                    scene["id"],
                    audio_dir,
                    project_root,
                    language=language,
                    **({"quality_check": True} if pin_model else {}),
                )
        elif provider == "uk":
            assert uk_service is not None
            staged_wav = staging / f"{scene['id']}.wav"

            def validate_candidate(candidate, scene=scene):
                if trim_edges:
                    trim_wav_edges(candidate)
                _check_clip_qa(
                    candidate,
                    scene["text"],
                    scene["id"],
                    audio_dir,
                    project_root,
                    refresh=True,
                    language=language,
                    **({"quality_check": True} if pin_model else {}),
                )

            actual_provider_id, actual_voice = uk_service.synthesize(
                scene["text"], staged_wav, validate=validate_candidate
            )
            dur = wav_duration(staged_wav)
            if dur <= 0:
                raise ValueError(f"Empty audio generated for {scene['id']}")
            cache = {
                "fingerprint": fingerprint,
                "provider": "uk",
                "model": actual_provider_id,
                "voice": effective_voice,
                "actual_voice": actual_voice,
                "provider_config": config_fingerprint,
                **({"pin_model": True} if pin_model else {}),
                **({"quality_check": True} if pin_model else {}),
                **(
                    {"timing_required": True}
                    if pin_model
                    and uk_service.pinned_provider is not None
                    and uk_service.pinned_provider.kind == "edge"
                    else {}
                ),
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
            if pinned_gemini_model is not None:
                # Retry transient failures without changing an established batch voice/model.
                candidate_models = [pinned_gemini_model] * 3
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
                    _check_clip_qa(
                        staged_wav,
                        scene["text"],
                        scene["id"],
                        audio_dir,
                        project_root,
                        refresh=True,
                        language=language,
                        **({"quality_check": True} if pin_model else {}),
                    )
                    last_error = None
                    break
                except (RecognitionError, ReviewRequiredError, FatalTTSError) as error:
                    raise _safe_gemini_error(error, api_key) from None
                except (RuntimeError, ValueError, httpx.HTTPError) as error:
                    last_error = _safe_gemini_error(error, api_key)
                    if isinstance(error, ValueError) and attempt_idx >= 1:
                        break
            if last_error is not None:
                raise last_error from None
            if language != "ru" or pin_model:
                pinned_gemini_model = actual_model
            dur = wav_duration(staged_wav)
            if dur <= 0:
                raise ValueError(f"Empty audio generated for {scene['id']}")
            cache = {
                "fingerprint": fingerprint,
                "model": actual_model,
                "voice": voice,
                "wav_sha256": hashlib.sha256(staged_wav.read_bytes()).hexdigest(),
                **({"trimmed": True} if trim_edges else {}),
                **({"pin_model": True} if pin_model else {}),
                **({"quality_check": True} if pin_model else {}),
            }
            status = "generated"
            already_trimmed = trim_edges
            if idx < len(scenes) - 1 and delay_s > 0:
                time.sleep(delay_s)

        if (trim_edges and not already_trimmed) or status == "generated":
            staged_wav = staging / f"{scene['id']}.wav"
            if status == "cached":
                shutil.copy2(wav_path, staged_wav)
                if cache.get("provider_timings"):
                    shutil.copy2(audio_dir / cache["provider_timings"], timing_sidecar(staged_wav))
                if trim_edges:
                    trim_wav_edges(staged_wav)
                    cache["trimmed"] = True
                _check_clip_qa(
                    staged_wav,
                    scene["text"],
                    scene["id"],
                    audio_dir,
                    project_root,
                    language=language,
                    **({"quality_check": True} if pin_model else {}),
                )
            dur = wav_duration(staged_wav)
            checksum = hashlib.sha256(staged_wav.read_bytes()).hexdigest()
            clip_fp = str(cache.get("fingerprint", fingerprint))
            wav_path = audio_dir / "clips" / f"{scene['id']}-{clip_fp[:12]}-{checksum[:12]}.wav"
            wav_path.parent.mkdir(exist_ok=True)
            cache.update(wav=str(wav_path.relative_to(audio_dir)), wav_sha256=checksum)
            evidence_path = timing_sidecar(staged_wav)
            if evidence_path.is_file():
                evidence_checksum = hashlib.sha256(evidence_path.read_bytes()).hexdigest()
                published_evidence = wav_path.with_name(
                    f"{wav_path.stem}-{evidence_checksum[:12]}.provider-timings.json"
                )
                shutil.copy2(evidence_path, published_evidence)
                cache.update(
                    provider_timings=str(published_evidence.relative_to(audio_dir)),
                    provider_timings_sha256=evidence_checksum,
                )
            staged_cache = staging / cache_path.name
            staged_cache.write_text(json.dumps(cache, indent=2), encoding="utf-8")
            staged_wav.replace(wav_path)
            staged_cache.replace(cache_path)

        validate_provider_timings(cache, audio_dir)
        if pin_model and cache.get("quality_check") is not True:
            cache["quality_check"] = True
            staged_cache = staging / cache_path.name
            staged_cache.write_text(json.dumps(cache, indent=2), encoding="utf-8")
            staged_cache.replace(cache_path)

        print(f"[{scene['id']}] ({status}) -> {wav_path.name} ({dur:.2f}s)")
        meta.append(
            {**scene, **cache, "language": language, "wav": str(wav_path.relative_to(audio_dir)), "duration": dur}
        )

    staged_manifest = staging / "manifest.json"
    staged_manifest.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    staged_manifest.replace(audio_dir / "manifest.json")
    print(f"Total audio duration: {sum(m['duration'] for m in meta):.2f}s")
    return meta
