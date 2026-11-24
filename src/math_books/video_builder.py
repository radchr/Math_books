"""End-to-end STEM-Basketball video build, audio concatenation, muxing, and verification."""

from __future__ import annotations

import dataclasses
import hashlib
import importlib
import json
import math
import os
import re
import subprocess
import tempfile
import wave
from fractions import Fraction
from pathlib import Path

from math_books.content_review import check_content_review, require_content_review
from math_books.tts_engine import audio_lock, valid_request_fingerprints, wav_duration
from math_books.voiceover_qa import require_manifest_quality, verify_manifest


@dataclasses.dataclass(frozen=True)
class VideoTopic:
    key: str
    video_dir: str
    scene_file: str
    scene_class: str
    output_name: str
    tts_module: str


TEST_VIDEOS_DIR = "test_videos"
PRODUCTION_VIDEOS_DIR = "videos"

VIDEO_TOPICS: dict[str, VideoTopic] = {
    "free_throws": VideoTopic(
        key="free_throws",
        video_dir="videos/video_free_throws",
        scene_file="src/math_books/free_throws_scene.py",
        scene_class="FreeThrowsBasketball",
        output_name="free_throws.mp4",
        tts_module="math_books.generate_free_throws_tts",
    ),
    "basketball": VideoTopic(
        key="basketball",
        video_dir="videos/video_basketball",
        scene_file="src/math_books/basketball_triangles_scene.py",
        scene_class="BasketballTriangles",
        output_name="basketball_triangles.mp4",
        tts_module="math_books.generate_tts",
    ),
    "ahrens": VideoTopic(
        key="ahrens",
        video_dir="videos/video_ahrens",
        scene_file="src/math_books/ahrens_basketball_scene.py",
        scene_class="AhrensBasketball",
        output_name="ahrens_basketball.mp4",
        tts_module="math_books.generate_ahrens_tts",
    ),
    "simpson": VideoTopic(
        key="simpson",
        video_dir="videos/video_simpson",
        scene_file="src/math_books/simpson_basketball_scene.py",
        scene_class="SimpsonBasketball",
        output_name="simpson_basketball.mp4",
        tts_module="math_books.generate_simpson_tts",
    ),
    "moneybart": VideoTopic(
        key="moneybart",
        video_dir="videos/video_moneybart",
        scene_file="src/math_books/moneybart_scene.py",
        scene_class="MoneyBartBasketball",
        output_name="moneybart_basketball.mp4",
        tts_module="math_books.generate_moneybart_tts",
    ),
    "hothand": VideoTopic(
        key="hothand",
        video_dir="videos/video_hothand",
        scene_file="src/math_books/hothand_scene.py",
        scene_class="HotHandBasketball",
        output_name="hothand_basketball.mp4",
        tts_module="math_books.generate_hothand_tts",
    ),
    "buzzer": VideoTopic(
        key="buzzer",
        video_dir="videos/video_buzzer",
        scene_file="src/math_books/buzzer_scene.py",
        scene_class="BuzzerBeaterBasketball",
        output_name="buzzer_basketball.mp4",
        tts_module="math_books.generate_buzzer_tts",
    ),
}


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def require_topic_review(topic: VideoTopic, base: Path) -> dict:
    scenes = importlib.import_module(topic.tts_module).SCENES
    return require_content_review(scenes, topic.video_dir, base, expected_scene_file=topic.scene_file)


def validate_topic_audio(topic: VideoTopic, base: Path) -> list[dict]:
    """Reject stale narration before spending time on a render."""
    require_topic_review(topic, base)
    path = base / topic.video_dir / "audio/manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    scenes = importlib.import_module(topic.tts_module).SCENES
    if [(s["id"], s["text"]) for s in manifest] != [(s["id"], s["text"]) for s in scenes]:
        raise ValueError(f"Stale script/audio manifest for {topic.key}; run math-books tts {topic.key}")
    for index, item in enumerate(manifest):
        if not all(key in item for key in ("fingerprint", "wav_sha256", "model", "voice")):
            raise ValueError(f"Untrusted legacy audio for {topic.key}; regenerate with math-books tts {topic.key}")
        if item["fingerprint"] not in valid_request_fingerprints(item["text"], item["voice"], index):
            raise ValueError(f"Stale audio provenance for {item['id']}; regenerate TTS")
        wav = path.parent / item["wav"]
        duration = float(item["duration"])
        if not math.isfinite(duration) or duration <= 0 or abs(wav_duration(wav) - duration) > 0.001:
            raise ValueError(f"Stale audio duration for {item['id']}; refresh TTS")
        if "wav_sha256" in item and hashlib.sha256(wav.read_bytes()).hexdigest() != item["wav_sha256"]:
            raise ValueError(f"Stale audio checksum for {item['id']}; refresh TTS")
    require_manifest_quality(path, manifest, base)
    return manifest


def verify_topic_audio(topic: VideoTopic, base: Path, *, refresh: bool = False) -> dict:
    """Verify topic audio manifest provenance and local ASR voiceover QA."""
    path = base / topic.video_dir / "audio/manifest.json"
    scenes = importlib.import_module(topic.tts_module).SCENES
    editorial = check_content_review(scenes, topic.video_dir, base, expected_scene_file=topic.scene_file)
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
            manifest = json.loads(path.read_text(encoding="utf-8"))
            if [(s["id"], s["text"]) for s in manifest] != [(s["id"], s["text"]) for s in scenes]:
                raise ValueError(f"Stale script/audio manifest for {topic.key}; run math-books tts {topic.key}")
            for index, item in enumerate(manifest):
                if not all(key in item for key in ("fingerprint", "wav_sha256", "model", "voice")):
                    raise ValueError(
                        f"Untrusted legacy audio for {topic.key}; regenerate with math-books tts {topic.key}"
                    )
                if item["fingerprint"] not in valid_request_fingerprints(item["text"], item["voice"], index):
                    raise ValueError(f"Stale audio provenance for {item['id']}; regenerate TTS")
                wav = path.parent / item["wav"]
                duration = float(item["duration"])
                if not math.isfinite(duration) or duration <= 0 or abs(wav_duration(wav) - duration) > 0.001:
                    raise ValueError(f"Stale audio duration for {item['id']}; refresh TTS")
                if hashlib.sha256(wav.read_bytes()).hexdigest() != item["wav_sha256"]:
                    raise ValueError(f"Stale audio checksum for {item['id']}; refresh TTS")
            qa = verify_manifest(path, manifest, base, refresh=refresh)
            return {"topic": topic.key, "path": str(path), "editorial": editorial, **qa}
        except (OSError, ValueError, KeyError, TypeError) as error:
            return {"topic": topic.key, "path": str(path), "ok": False, "editorial": editorial, "issues": [str(error)]}


def render_fingerprint(topic: VideoTopic, base: Path, manifest: list[dict]) -> str:
    """Bind the silent render to its scene, shared UI and exact audio timing."""
    digest = hashlib.sha256()
    for path in (base / topic.scene_file, base / "src/math_books/video_ui.py", base / "src/math_books/lesson_math.py"):
        digest.update(path.read_bytes())
    digest.update(json.dumps([(s["id"], s["duration"]) for s in manifest]).encode())
    return digest.hexdigest()


def topic_status_summary(topic: VideoTopic, base: Path) -> dict:
    """Return a unified readiness summary across editorial review, audio QA, final video, and test archive."""
    scenes = importlib.import_module(topic.tts_module).SCENES
    editorial = check_content_review(scenes, topic.video_dir, base, expected_scene_file=topic.scene_file)
    review_state = "approved" if editorial["ok"] else "blocked"

    manifest_path = base / topic.video_dir / "audio" / "manifest.json"
    if not manifest_path.is_file():
        audio_state = "missing"
    elif not editorial["ok"]:
        audio_state = "blocked"
    else:
        try:
            validate_topic_audio(topic, base)
            audio_state = "verified"
        except (OSError, ValueError, KeyError, TypeError):
            audio_state = "stale"

    video_path = base / topic.video_dir / topic.output_name
    build_json = video_path.with_suffix(".build.json")
    if not video_path.is_file():
        video_state = "missing"
    elif not editorial["ok"] or audio_state != "verified" or not build_json.is_file():
        video_state = "stale"
    else:
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            provenance = json.loads(build_json.read_text(encoding="utf-8"))
            fingerprint = render_fingerprint(topic, base, manifest)
            audio_hashes = [
                hashlib.sha256((base / topic.video_dir / "audio" / s["wav"]).read_bytes()).hexdigest() for s in manifest
            ]
            if (
                provenance.get("fingerprint") == fingerprint
                and provenance.get("audio_sha256") == audio_hashes
                and provenance.get("video_sha256") == hashlib.sha256(video_path.read_bytes()).hexdigest()
            ):
                video_state = "verified"
            else:
                video_state = "stale"
        except (OSError, ValueError, KeyError, TypeError):
            video_state = "stale"

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
        "ready": review_state == "approved" and audio_state == "verified" and video_state == "verified",
    }


def verify_topic_video(topic: VideoTopic, base: Path, *, check_silence: bool = True) -> dict:
    scenes = importlib.import_module(topic.tts_module).SCENES
    editorial = check_content_review(scenes, topic.video_dir, base, expected_scene_file=topic.scene_file)
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
        manifest = validate_topic_audio(topic, base)
        provenance = json.loads(video.with_suffix(".build.json").read_text())
        fingerprint = render_fingerprint(topic, base, manifest)
        audio_hashes = [
            hashlib.sha256((base / topic.video_dir / "audio" / s["wav"]).read_bytes()).hexdigest() for s in manifest
        ]
        if (
            provenance["fingerprint"] != fingerprint
            or provenance["audio_sha256"] != audio_hashes
            or provenance["video_sha256"] != hashlib.sha256(video.read_bytes()).hexdigest()
        ):
            raise ValueError("Stale final video: source, audio or output changed; rebuild")
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


def render_silent_video(topic: VideoTopic, root: Path | None = None) -> Path:
    """Render silent 9:16 Manim video and return path to the rendered MP4."""
    base = root or project_root()
    validate_topic_audio(topic, base)
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
    env = {**os.environ, "MATH_BOOKS_MANIFEST_PATH": str(manifest_path)}
    subprocess.run(cmd, check=True, cwd=base, env=env)

    matches = sorted(media_dir.rglob(silent_name), key=lambda p: p.stat().st_mtime, reverse=True)
    if not matches:
        raise FileNotFoundError(f"Rendered silent video {silent_name} not found in {media_dir}")
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
        fps = float(Fraction(v_stream["avg_frame_rate"]))
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
) -> list[Path]:
    """Extract 1 midpoint PNG frame per scene for visual QA."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
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


def build_video(topic_key: str, *, skip_render: bool = False, root: Path | None = None) -> dict:
    if topic_key not in VIDEO_TOPICS:
        raise KeyError(f"Unknown topic: {topic_key}")
    base = root or project_root()
    require_topic_review(VIDEO_TOPICS[topic_key], base)
    with audio_lock(base / VIDEO_TOPICS[topic_key].video_dir / "audio"):
        return _build_video(topic_key, skip_render=skip_render, root=base)


def _build_video(topic_key: str, *, skip_render: bool = False, root: Path | None = None) -> dict:
    """Run full video build: render silent Manim -> concat WAV -> mux -> verify."""
    if topic_key not in VIDEO_TOPICS:
        raise KeyError(f"Unknown topic '{topic_key}'. Available: {', '.join(VIDEO_TOPICS)}")

    base = root or project_root()
    topic = VIDEO_TOPICS[topic_key]
    manifest_path = base / topic.video_dir / "audio" / "manifest.json"
    out_mp4 = base / topic.video_dir / topic.output_name
    manifest = validate_topic_audio(topic, base)
    fingerprint = render_fingerprint(topic, base, manifest)

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
        silent_mp4 = render_silent_video(topic, root=base)
        silent_mp4.with_suffix(".render.json").write_text(
            json.dumps(
                {"fingerprint": fingerprint, "video_sha256": hashlib.sha256(silent_mp4.read_bytes()).hexdigest()}
            )
        )

    with tempfile.TemporaryDirectory(dir=out_mp4.parent) as tmpdir:
        full_wav = Path(tmpdir) / f"{topic.key}_full_audio.wav"
        audio_dur = concat_audio_from_manifest(manifest_path, full_wav)
        print(f"Concatenated audio: {audio_dur:.2f}s")
        candidate = Path(tmpdir) / out_mp4.name
        mux_audio_video(silent_mp4, full_wav, candidate)
        report = verify_video(candidate)
        if report["ok"]:
            provenance = {
                "fingerprint": fingerprint,
                "audio_sha256": [
                    hashlib.sha256((manifest_path.parent / s["wav"]).read_bytes()).hexdigest() for s in manifest
                ],
                "video_sha256": hashlib.sha256(candidate.read_bytes()).hexdigest(),
            }
            staged_provenance = Path(tmpdir) / "build.json"
            staged_provenance.write_text(json.dumps(provenance, indent=2))
            candidate.replace(out_mp4)
            staged_provenance.replace(out_mp4.with_suffix(".build.json"))
        report["path"] = str(out_mp4)

    print(f"Built {out_mp4} -> {json.dumps(report, ensure_ascii=False)}")
    return report
