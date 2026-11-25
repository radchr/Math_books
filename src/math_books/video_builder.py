"""End-to-end STEM-Basketball video build, audio concatenation, muxing, and verification."""

from __future__ import annotations

import fcntl
import hashlib
import json
import math
import os
import re
import subprocess
import tempfile
import wave
from contextlib import contextmanager
from fractions import Fraction
from pathlib import Path

from math_books.content_review import check_content_review, require_content_review
from math_books.cue_timeline import event_timeline, timed_event_timeline, validate_event_log
from math_books.languages import validate_language
from math_books.lessons import lesson_digest
from math_books.media_io import atomic_json, audio_lock, wav_duration
from math_books.music_tracks import render_music_bed, resolve_music_track
from math_books.topics import PRODUCTION_VIDEOS_DIR as PRODUCTION_VIDEOS_DIR
from math_books.topics import TEST_VIDEOS_DIR as TEST_VIDEOS_DIR
from math_books.topics import VIDEO_TOPICS as VIDEO_TOPICS
from math_books.topics import VideoTopic as VideoTopic
from math_books.topics import available_topics as available_topics
from math_books.topics import get_topic as get_topic
from math_books.topics import project_root as project_root
from math_books.topics import topic_scenes as topic_scenes
from math_books.tts_engine import valid_request_fingerprints
from math_books.uk_tts_providers import build_ukrainian_providers, profile_fingerprint, validate_provider_timings
from math_books.voiceover_qa import require_manifest_quality, timing_snapshot, verify_manifest


def require_topic_review(topic: VideoTopic, base: Path) -> dict:
    scenes = topic_scenes(topic, base)
    return require_content_review(
        scenes, topic.video_dir, base, expected_scene_file=topic.scene_file, language=topic.language
    )


def _expected_audio_fingerprints(topic: VideoTopic, base: Path, item: dict, index: int) -> set[str]:
    language = validate_language(item.get("language", "ru"))
    if language != topic.language or (topic.lesson_file and "language" not in item):
        raise ValueError("Audio manifest language does not match lesson")
    if topic.lesson_file and not item.get("pin_model"):
        raise ValueError("Future lesson audio requires a pinned batch voice/model")
    if topic.lesson_file and item.get("quality_check") is not True:
        raise ValueError("Future lesson audio requires current acoustic QA; refresh TTS")
    provider = item.get("provider", "gemini")
    if provider not in ("gemini", "uk"):
        raise ValueError("Unsupported audio provider")
    config = None
    if provider == "uk":
        if language != "uk":
            raise ValueError("Ukrainian provider requires uk language")
        profile, providers = build_ukrainian_providers(base, profile_id=item["voice"])
        config = profile_fingerprint(profile, providers)
        if item.get("provider_config") != config:
            raise ValueError("Ukrainian voice profile changed; regenerate audio")
    return valid_request_fingerprints(
        item["text"],
        item["voice"],
        index,
        provider=provider,
        language=language,
        provider_config=config,
        pin_model=item.get("pin_model", False),
    )


def _validate_batch_identity(topic: VideoTopic, manifest: list[dict]) -> None:
    if (
        topic.lesson_file
        and len({(s.get("provider", "gemini"), s["model"], s.get("actual_voice", s["voice"])) for s in manifest}) != 1
    ):
        raise ValueError("Future lesson audio mixes provider/model/voice identities")


def _validate_audio_manifest(topic: VideoTopic, base: Path) -> list[dict]:
    """Validate common provenance/media invariants without running or refreshing ASR."""
    path = base / topic.video_dir / "audio/manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    scenes = topic_scenes(topic, base)
    if not isinstance(manifest, list) or not manifest or not all(isinstance(item, dict) for item in manifest):
        raise ValueError("Audio manifest must be a nonempty list of clips")
    if [(s["id"], s["text"]) for s in manifest] != [(s["id"], s["text"]) for s in scenes]:
        raise ValueError(f"Stale script/audio manifest for {topic.key}; run math-books tts {topic.key}")
    for index, item in enumerate(manifest):
        if not all(key in item for key in ("fingerprint", "wav_sha256", "model", "voice")):
            raise ValueError(f"Untrusted legacy audio for {topic.key}; regenerate with math-books tts {topic.key}")
        if item["fingerprint"] not in _expected_audio_fingerprints(topic, base, item, index):
            raise ValueError(f"Stale audio provenance for {item['id']}; regenerate TTS")
        wav = path.parent / item["wav"]
        duration = float(item["duration"])
        if not math.isfinite(duration) or duration <= 0 or abs(wav_duration(wav) - duration) > 0.001:
            raise ValueError(f"Stale audio duration for {item['id']}; refresh TTS")
        if hashlib.sha256(wav.read_bytes()).hexdigest() != item["wav_sha256"]:
            raise ValueError(f"Stale audio checksum for {item['id']}; refresh TTS")
        validate_provider_timings(item, path.parent)
    _validate_batch_identity(topic, manifest)
    return manifest


def validate_topic_audio(topic: VideoTopic, base: Path) -> list[dict]:
    """Reject stale narration before spending time on a render (caller holds audio lock)."""
    require_topic_review(topic, base)
    manifest = _validate_audio_manifest(topic, base)
    require_manifest_quality(base / topic.video_dir / "audio/manifest.json", manifest, base)
    return manifest


def verify_topic_audio(topic: VideoTopic, base: Path, *, refresh: bool = False) -> dict:
    """Verify topic audio manifest provenance and local ASR voiceover QA."""
    path = base / topic.video_dir / "audio/manifest.json"
    scenes = topic_scenes(topic, base)
    editorial = check_content_review(
        scenes, topic.video_dir, base, expected_scene_file=topic.scene_file, language=topic.language
    )
    if not editorial["ok"]:
        return {
            "topic": topic.key,
            "path": str(path),
            "ok": False,
            "editorial": editorial,
            "issues": ["Content review blocked audio verification: " + "; ".join(editorial["issues"])],
        }
    with audio_lock(base / topic.video_dir / "audio"):
        try:
            manifest = _validate_audio_manifest(topic, base)
            qa = verify_manifest(path, manifest, base, refresh=refresh)
            return {"topic": topic.key, "path": str(path), "editorial": editorial, **qa}
        except (OSError, ValueError, KeyError, TypeError) as error:
            return {"topic": topic.key, "path": str(path), "ok": False, "editorial": editorial, "issues": [str(error)]}


def _is_music_only(scenes: list[dict]) -> bool:
    return bool(scenes) and scenes[0].get("audio_mode") == "music_only"


def render_fingerprint(
    topic: VideoTopic, base: Path, manifest: list[dict], *, snapshot: dict | None = None, events: dict | None = None
) -> str:
    """Bind the silent render to its scene, shared UI and exact audio timing."""
    digest = hashlib.sha256()
    for path in (base / topic.scene_file, base / "src/math_books/video_ui.py", base / "src/math_books/lesson_math.py"):
        digest.update(path.read_bytes())
    digest.update(json.dumps([(s["id"], s["duration"]) for s in manifest]).encode())
    if topic.lesson_file:
        scenes = topic_scenes(topic, base)
        digest.update(topic.language.encode())
        digest.update(lesson_digest(scenes).encode())
        for name in ("languages.py", "lessons.py", "cue_timeline.py"):
            digest.update((base / "src/math_books" / name).read_bytes())
        from math_books.visual_blocks import visual_source_files

        for source_file in visual_source_files():
            digest.update(source_file.read_bytes())
        if _is_music_only(scenes):
            track_id = str(scenes[0]["music_track"])
            track_path, track_meta = resolve_music_track(base, track_id)
            digest.update((base / "src/math_books/music_tracks.py").read_bytes())
            digest.update(track_id.encode())
            digest.update(track_meta["sha256"].encode())
            digest.update(track_path.read_bytes())
            if events is None:
                events = timed_event_timeline(scenes)
            digest.update(json.dumps(events, sort_keys=True).encode())
        else:
            if snapshot is None:
                snapshot = timing_snapshot(base / topic.video_dir / "audio/manifest.json", manifest, base)
            digest.update(json.dumps(snapshot, sort_keys=True).encode())
            if events is None:
                events = event_timeline(scenes, manifest, snapshot, topic.language)
            digest.update(json.dumps(events, sort_keys=True).encode())
    return digest.hexdigest()


@contextmanager
def _read_status_lock(audio_dir: Path):
    """Probe an existing writer lock without creating directories or a lock file.

    With no existing lock there is no synchronized snapshot, so every presence
    result remains explicitly unverified. Full verification uses audio_lock.
    """
    try:
        lock = (audio_dir / ".pipeline.lock").open("rb")
    except FileNotFoundError:
        yield False
        return
    with lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError:
            yield True
            return
        try:
            yield False
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def _audio_presence(topic: VideoTopic, base: Path, scenes: list[dict], approved: bool) -> str:
    """Inspect cheap metadata/file presence only; do not decode, hash or run ASR."""
    if _is_music_only(scenes):
        if not approved:
            return "blocked"
        return "music_only"
    path = base / topic.video_dir / "audio/manifest.json"
    if not path.is_file():
        return "missing"
    if not approved:
        return "blocked"
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(manifest, list) or not manifest or not all(isinstance(item, dict) for item in manifest):
            return "stale"
        if [(item["id"], item["text"]) for item in manifest] != [(scene["id"], scene["text"]) for scene in scenes]:
            return "stale"
        for item in manifest:
            if not all(key in item for key in ("fingerprint", "wav_sha256", "model", "voice")):
                return "stale"
            if item.get("language", "ru") != topic.language:
                return "stale"
            duration = float(item["duration"])
            if not math.isfinite(duration) or duration <= 0:
                return "stale"
            wav = path.parent / item["wav"]
            if not wav.resolve().is_relative_to(path.parent.resolve()) or not wav.is_file():
                return "stale"
        return "unverified"
    except (OSError, ValueError, KeyError, TypeError):
        return "stale"


def _video_presence(topic: VideoTopic, base: Path, audio_state: str, approved: bool) -> str:
    video = base / topic.video_dir / topic.output_name
    if not video.is_file():
        return "missing"
    if not approved:
        return "blocked"
    if audio_state not in ("unverified", "music_only"):
        return "stale"
    try:
        provenance = json.loads(video.with_suffix(".build.json").read_text(encoding="utf-8"))
        has_audio_proof = (
            isinstance(provenance.get("music_sha256"), str)
            if audio_state == "music_only"
            else isinstance(provenance.get("audio_sha256"), list)
        )
        if (
            not isinstance(provenance, dict)
            or not isinstance(provenance.get("fingerprint"), str)
            or not isinstance(provenance.get("video_sha256"), str)
            or not has_audio_proof
        ):
            return "stale"
    except (OSError, ValueError, TypeError):
        return "stale"
    return "unverified"


def topic_status_summary(topic: VideoTopic, base: Path) -> dict:
    """Read-only inventory. ``unverified`` means present, never a readiness claim.

    No WAV/MP4 contents are hashed or decoded, ASR receipts are not refreshed,
    and no subprocess/lock-file creation occurs. Use verify[-audio] for proof.
    """
    scenes = topic_scenes(topic, base)
    editorial = check_content_review(
        scenes, topic.video_dir, base, expected_scene_file=topic.scene_file, language=topic.language
    )
    review_state = "approved" if editorial["ok"] else "blocked"

    try:
        with _read_status_lock(base / topic.video_dir / "audio") as busy:
            if busy:
                audio_state = video_state = "busy"
            else:
                audio_state = _audio_presence(topic, base, scenes, editorial["ok"])
                video_state = _video_presence(topic, base, audio_state, editorial["ok"])
    except OSError:
        # Concurrent removal or inaccessible lock state must not crash list.
        audio_state = video_state = "busy"

    test_mp4 = base / TEST_VIDEOS_DIR / Path(topic.video_dir).name / topic.output_name
    return {
        "topic": topic.key,
        "scene_class": topic.scene_class,
        "output": f"{topic.video_dir}/{topic.output_name}",
        "review": review_state,
        "audio": audio_state,
        "video": video_state,
        "test_archive": f"{TEST_VIDEOS_DIR}/{Path(topic.video_dir).name}/{topic.output_name}"
        if test_mp4.is_file()
        else None,
        "ready": False,
        "verification": "not_run",
    }


def verify_topic_video(topic: VideoTopic, base: Path, *, check_silence: bool = True) -> dict:
    scenes = topic_scenes(topic, base)
    editorial = check_content_review(
        scenes, topic.video_dir, base, expected_scene_file=topic.scene_file, language=topic.language
    )
    if not editorial["ok"]:
        return {
            "path": str(base / topic.video_dir / topic.output_name),
            "ok": False,
            "editorial": editorial,
            "media_checked": False,
            "issues": ["Content review blocked verification: " + "; ".join(editorial["issues"])],
        }
    with audio_lock(base / topic.video_dir / "audio"):
        report = _verify_topic_video(topic, base, check_silence=check_silence)
        report.update(editorial=editorial, media_checked=True)
        return report


def _verify_topic_video(topic: VideoTopic, base: Path, *, check_silence: bool = True) -> dict:
    """Verify both the media streams and that this MP4 was built from current inputs."""
    video = base / topic.video_dir / topic.output_name
    report = verify_video(video, check_silence=check_silence)
    try:
        scenes = topic_scenes(topic, base)
        provenance = json.loads(video.with_suffix(".build.json").read_text())
        if _is_music_only(scenes):
            track_id = str(scenes[0]["music_track"])
            _, track_meta = resolve_music_track(base, track_id)
            manifest = [{"id": s["id"], "duration": float(s["duration_s"])} for s in scenes]
            events = timed_event_timeline(scenes)
            fingerprint = render_fingerprint(topic, base, manifest, events=events)
            if (
                provenance.get("audio_mode") != "music_only"
                or provenance.get("music_track") != track_id
                or provenance.get("music_sha256") != track_meta["sha256"]
                or provenance.get("fingerprint") != fingerprint
                or provenance.get("video_sha256") != hashlib.sha256(video.read_bytes()).hexdigest()
            ):
                raise ValueError("Stale final music_only video: source, music track, or output changed; rebuild")
            validate_event_log(events, provenance.get("events", []))
        else:
            manifest = validate_topic_audio(topic, base)
            snapshot = None
            events = None
            if topic.lesson_file:
                snapshot = timing_snapshot(base / topic.video_dir / "audio/manifest.json", manifest, base)
                events = event_timeline(scenes, manifest, snapshot, topic.language)
            fingerprint = render_fingerprint(topic, base, manifest, snapshot=snapshot, events=events)
            audio_hashes = [
                hashlib.sha256((base / topic.video_dir / "audio" / s["wav"]).read_bytes()).hexdigest() for s in manifest
            ]
            if (
                provenance["fingerprint"] != fingerprint
                or provenance["audio_sha256"] != audio_hashes
                or provenance["video_sha256"] != hashlib.sha256(video.read_bytes()).hexdigest()
            ):
                raise ValueError("Stale final video: source, audio or output changed; rebuild")
            if events is not None:
                validate_event_log(events, provenance.get("events", []))
    except (OSError, ValueError, KeyError, TypeError) as error:
        report["issues"].append(f"Build provenance failed: {error}")
    report["ok"] = not report["issues"]
    return report


def concat_audio_from_manifest(
    manifest_path: Path,
    out_wav: Path,
    *,
    gap_ms: int = 400,
    tail_ms: int = 300,
) -> float:
    """Concatenate scene WAV files with exact inter-scene silence gaps using stdlib wave."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not manifest:
        raise ValueError(f"Empty audio manifest: {manifest_path}")

    wav_paths = [manifest_path.parent / item["wav"] for item in manifest]
    for p in wav_paths:
        if not p.exists():
            raise FileNotFoundError(f"Missing scene WAV: {p}")

    params = None
    chunks: list[bytes] = []

    for idx, p in enumerate(wav_paths):
        with wave.open(str(p), "rb") as wf:
            cur = (wf.getnchannels(), wf.getsampwidth(), wf.getframerate())
            if params is None:
                params = cur
            elif cur != params:
                raise ValueError(f"WAV format mismatch in {p.name}: {cur} != {params}")
            chunks.append(wf.readframes(wf.getnframes()))

        nch, sw, fr = params
        silence_ms = gap_ms if idx < len(wav_paths) - 1 else tail_ms
        if silence_ms > 0:
            n_frames = int(round(fr * silence_ms / 1000.0))
            chunks.append(b"\x00" * (n_frames * nch * sw))

    assert params is not None
    nch, sw, fr = params
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out_wav), "wb") as out:
        out.setnchannels(nch)
        out.setsampwidth(sw)
        out.setframerate(fr)
        for chunk in chunks:
            out.writeframes(chunk)

    with wave.open(str(out_wav), "rb") as wf:
        return wf.getnframes() / float(wf.getframerate())


def render_silent_video(
    topic: VideoTopic, root: Path | None = None, *, snapshot: dict | None = None, events: dict | None = None
) -> Path:
    """Render silent 9:16 Manim video and return path to the rendered MP4."""
    base = root or project_root()
    scenes = topic_scenes(topic, base)
    music_only = _is_music_only(scenes)
    manifest = (
        [{"id": s["id"], "duration": float(s["duration_s"])} for s in scenes]
        if music_only
        else validate_topic_audio(topic, base)
    )
    manifest_path = (base / topic.video_dir / "audio" / "manifest.json").resolve()
    media_dir = base / topic.video_dir / "media"
    silent_name = f"{topic.key}_silent.mp4"
    cmd = [
        "manim",
        "render",
        "--media_dir",
        str(media_dir),
        "-o",
        silent_name,
        str(base / topic.scene_file),
        topic.scene_class,
    ]
    env = {**os.environ}
    if not music_only:
        env["MATH_BOOKS_MANIFEST_PATH"] = str(manifest_path)
    event_records = []
    if topic.lesson_file is not None:
        env.update(MATH_BOOKS_LANGUAGE=topic.language, MATH_BOOKS_LESSON_PATH=str((base / topic.lesson_file).resolve()))
        staging_parent = manifest_path.parent
        staging_parent.mkdir(parents=True, exist_ok=True)
        if music_only:
            if events is None:
                events = timed_event_timeline(scenes)
        else:
            # Snapshot once; Manim must consume the exact word evidence bound by provenance.
            if snapshot is None:
                snapshot = timing_snapshot(manifest_path, manifest, base)
            if events is None:
                events = event_timeline(scenes, manifest, snapshot, topic.language)
        with tempfile.TemporaryDirectory(dir=staging_parent) as staging:
            if not music_only and snapshot is not None:
                snapshot_path = Path(staging) / "timings.json"
                snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")
                env["MATH_BOOKS_TIMING_SNAPSHOT_PATH"] = str(snapshot_path)
            events_path = Path(staging) / "events.json"
            log_path = Path(staging) / "event_log.json"
            events_path.write_text(json.dumps(events), encoding="utf-8")
            env.update(MATH_BOOKS_EVENT_TIMELINE_PATH=str(events_path), MATH_BOOKS_EVENT_LOG_PATH=str(log_path))
            subprocess.run(cmd, check=True, cwd=base, env=env)
            if any(events.values()):
                event_records = json.loads(log_path.read_text(encoding="utf-8"))
                validate_event_log(events, event_records)
    else:
        subprocess.run(cmd, check=True, cwd=base, env=env)

    matches = sorted(media_dir.rglob(silent_name), key=lambda p: p.stat().st_mtime, reverse=True)
    if not matches:
        raise FileNotFoundError(f"Rendered silent video {silent_name} not found in {media_dir}")
    if topic.lesson_file:
        atomic_json(matches[0].with_suffix(".events.json"), event_records)
    return matches[0]


def mux_audio_video(silent_mp4: Path, audio_wav: Path, out_mp4: Path) -> None:
    """Mux silent H.264 video with WAV audio into final AAC/MP4."""
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(silent_mp4),
        "-i",
        str(audio_wav),
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        str(out_mp4),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def verify_video(mp4_path: Path, *, check_silence: bool = True) -> dict:
    """Inspect rendered MP4 via ffprobe (and optional ffmpeg silencedetect)."""
    if not mp4_path.exists():
        raise FileNotFoundError(f"Video not found: {mp4_path}")

    probe_cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "stream=codec_type,codec_name,width,height,duration,avg_frame_rate",
        "-of",
        "json",
        str(mp4_path),
    ]
    proc = subprocess.run(probe_cmd, check=True, capture_output=True, text=True)
    streams = json.loads(proc.stdout).get("streams", [])

    v_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    a_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

    issues: list[str] = []
    if not v_stream:
        issues.append("Missing video stream")
    else:
        if (v_stream.get("width"), v_stream.get("height")) != (1080, 1920):
            issues.append(f"Unexpected resolution: {v_stream.get('width')}x{v_stream.get('height')}")
    if not a_stream:
        issues.append("Missing audio stream")

    def duration(stream, name):
        try:
            value = float(stream["duration"])
            if math.isfinite(value) and value > 0:
                return value
        except (TypeError, KeyError, ValueError):
            pass
        issues.append(f"Invalid {name} duration")
        return 0.0

    v_dur = duration(v_stream, "video")
    a_dur = duration(a_stream, "audio")
    try:
        fps = float(Fraction(v_stream["avg_frame_rate"])) if v_stream else 0.0
    except (TypeError, KeyError, ValueError, ZeroDivisionError):
        fps = 0.0
    if abs(fps - 30) > 0.01:
        issues.append(f"Unexpected frame rate: {fps:g} (expected 30)")
    delta = abs(v_dur - a_dur)
    if v_stream and a_stream and delta > 1.0:
        issues.append(f"Audio/video duration mismatch: video={v_dur:.2f}s, audio={a_dur:.2f}s")

    long_silences: list[float] = []
    if check_silence and a_stream:
        sil_cmd = [
            "ffmpeg",
            "-i",
            str(mp4_path),
            "-af",
            f"silencedetect=noise=-40dB:d={min(1.2, a_dur * 0.95):.6f}",
            "-f",
            "null",
            "-",
        ]
        sil_proc = subprocess.run(sil_cmd, capture_output=True, text=True)
        if sil_proc.returncode != 0:
            issues.append("Silence detection failed")
        for m in re.finditer(r"silence_duration:\s*([0-9.]+)", sil_proc.stderr):
            long_silences.append(float(m.group(1)))
        if long_silences:
            issues.append(f"Long audio silence detected: {long_silences}")

    return {
        "path": str(mp4_path),
        "width": v_stream.get("width") if v_stream else None,
        "height": v_stream.get("height") if v_stream else None,
        "fps": fps,
        "video_duration": round(v_dur, 2),
        "audio_duration": round(a_dur, 2),
        "duration_delta": round(delta, 2),
        "long_silences_s": long_silences,
        "issues": issues,
        "ok": len(issues) == 0,
    }


def extract_preview_frames(
    mp4_path: Path,
    manifest_path: Path,
    out_dir: Path,
    *,
    gap_s: float = 0.4,
    scenes: list[dict] | None = None,
) -> list[Path]:
    """Extract 1 midpoint PNG frame per scene for visual QA."""
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    elif scenes is not None:
        manifest = [{"id": s["id"], "duration": float(s["duration_s"])} for s in scenes]
    else:
        raise FileNotFoundError(f"Missing audio manifest: {manifest_path}")
    out_dir.mkdir(parents=True, exist_ok=True)
    frames: list[Path] = []
    cursor = 0.0
    for item in manifest:
        dur = float(item["duration"])
        ts = cursor + dur * 0.55
        out_png = out_dir / f"{item['id']}.png"
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-ss",
                f"{ts:.2f}",
                "-i",
                str(mp4_path),
                "-vframes",
                "1",
                str(out_png),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        frames.append(out_png)
        cursor += dur + gap_s
    return frames


def build_video(topic_key: str, *, skip_render: bool = False, root: Path | None = None, language: str = "ru") -> dict:
    base = root or project_root()
    topic = get_topic(topic_key, language, base)
    require_topic_review(topic, base)
    with audio_lock(base / topic.video_dir / "audio"):
        return _build_video(topic_key, skip_render=skip_render, root=base, language=language)


def _build_video(topic_key: str, *, skip_render: bool = False, root: Path | None = None, language: str = "ru") -> dict:
    """Run full video build: render silent Manim -> concat WAV or music bed -> mux -> verify."""
    base = root or project_root()
    topic = get_topic(topic_key, language, base)
    scenes = topic_scenes(topic, base)
    music_only = _is_music_only(scenes)
    manifest_path = base / topic.video_dir / "audio" / "manifest.json"
    out_mp4 = base / topic.video_dir / topic.output_name
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    if music_only:
        track_id = str(scenes[0]["music_track"])
        track_path, track_meta = resolve_music_track(base, track_id)
        manifest = [{"id": s["id"], "duration": float(s["duration_s"])} for s in scenes]
        snapshot = None
        events = timed_event_timeline(scenes)
    else:
        track_id = ""
        track_path = None
        track_meta = {}
        manifest = validate_topic_audio(topic, base)
        snapshot = timing_snapshot(manifest_path, manifest, base) if topic.lesson_file else None
        events = event_timeline(scenes, manifest, snapshot, topic.language) if snapshot is not None else {}
    fingerprint = render_fingerprint(topic, base, manifest, snapshot=snapshot, events=events)

    if skip_render:
        media_dir = base / topic.video_dir / "media"
        matches = sorted(
            media_dir.rglob(f"{topic.key}_silent.mp4"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not matches:
            raise FileNotFoundError(f"No existing silent video found in {media_dir}")
        silent_mp4 = matches[0]
        signature = silent_mp4.with_suffix(".render.json")
        provenance = json.loads(signature.read_text()) if signature.exists() else {}
        if (
            provenance.get("fingerprint") != fingerprint
            or provenance.get("video_sha256") != hashlib.sha256(silent_mp4.read_bytes()).hexdigest()
        ):
            raise ValueError("Stale or untracked silent render; rebuild without --skip-render")
    else:
        silent_mp4 = render_silent_video(topic, root=base, snapshot=snapshot, events=events)
        atomic_json(
            silent_mp4.with_suffix(".render.json"),
            {"fingerprint": fingerprint, "video_sha256": hashlib.sha256(silent_mp4.read_bytes()).hexdigest()},
        )

    event_records = []
    if topic.lesson_file and any(events.values()):
        event_records = json.loads(silent_mp4.with_suffix(".events.json").read_text(encoding="utf-8"))
        validate_event_log(events, event_records)

    with tempfile.TemporaryDirectory(dir=out_mp4.parent) as tmpdir:
        full_wav = Path(tmpdir) / f"{topic.key}_full_audio.wav"
        if music_only:
            assert track_path is not None
            total_dur = sum(float(s["duration_s"]) for s in scenes) + 0.4 * max(0, len(scenes) - 1) + 0.3
            audio_dur = render_music_bed(track_path, full_wav, total_dur)
            print(f"Rendered music bed ({track_id}): {audio_dur:.2f}s")
        else:
            audio_dur = concat_audio_from_manifest(manifest_path, full_wav)
            print(f"Concatenated audio: {audio_dur:.2f}s")
        candidate = Path(tmpdir) / out_mp4.name
        mux_audio_video(silent_mp4, full_wav, candidate)
        report = verify_video(candidate)
        if report["ok"]:
            if music_only:
                provenance = {
                    "fingerprint": fingerprint,
                    "audio_mode": "music_only",
                    "music_track": track_id,
                    "music_sha256": track_meta["sha256"],
                    "video_sha256": hashlib.sha256(candidate.read_bytes()).hexdigest(),
                    **({"events": event_records} if topic.lesson_file else {}),
                }
            else:
                provenance = {
                    "fingerprint": fingerprint,
                    "audio_sha256": [
                        hashlib.sha256((manifest_path.parent / str(s["wav"])).read_bytes()).hexdigest()
                        for s in manifest
                    ],
                    "video_sha256": hashlib.sha256(candidate.read_bytes()).hexdigest(),
                    **({"events": event_records} if topic.lesson_file else {}),
                }
            staged_provenance = Path(tmpdir) / "build.json"
            staged_provenance.write_text(json.dumps(provenance, indent=2))
            candidate.replace(out_mp4)
            staged_provenance.replace(out_mp4.with_suffix(".build.json"))
        report["path"] = str(out_mp4)

    print(f"Built {out_mp4} -> {json.dumps(report, ensure_ascii=False)}")
    return report
