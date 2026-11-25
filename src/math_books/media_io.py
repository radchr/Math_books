"""Low-level WAV, process locking and atomic sidecar I/O without pipeline imports."""

from __future__ import annotations

import fcntl
import json
import os
import tempfile
import wave
from contextlib import contextmanager
from pathlib import Path


def wav_duration(wav_path: Path) -> float:
    with wave.open(str(wav_path), "rb") as source:
        count = source.getnframes()
        pcm = source.readframes(count)
        if len(pcm) != count * source.getnchannels() * source.getsampwidth():
            raise ValueError(f"Truncated WAV PCM: {wav_path}")
        return count / float(source.getframerate())


@contextmanager
def audio_lock(audio_dir: Path):
    """Exclusive writer lock; read-only status probes never call this helper."""
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


def atomic_json(path: Path, value: object) -> None:
    """Publish complete JSON, preserving the old sidecar on serialization/I/O failure."""
    encoded = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, encoding="utf-8", delete=False) as output:
            temporary = Path(output.name)
            output.write(encoded)
            output.flush()
            os.fsync(output.fileno())
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
