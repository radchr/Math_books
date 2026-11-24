"""Multi-provider Ukrainian TTS fallback chain (StyleTTS2 -> Piper -> Edge TTS) with voice pinning.

Adapted from radchr/Anime (NauKadr) and standardized to 24 kHz mono 16-bit PCM WAV so clips plug
directly into Math_books' lossless stdlib `wave` concatenation and local ASR QA pipeline.
"""

from __future__ import annotations

import asyncio
import dataclasses
import shutil
import subprocess
import tempfile
import threading
import tomllib
import wave
from collections.abc import Coroutine, Mapping
from pathlib import Path
from typing import Any, Protocol


class UkrainianVoiceProvider(Protocol):
    provider_id: str
    voice: str
    kind: str

    @property
    def settings(self) -> Mapping[str, object]: ...

    def synthesize_wav(self, text: str, out_wav: Path) -> None: ...


@dataclasses.dataclass(frozen=True)
class ProviderConfig:
    provider_id: str
    kind: str
    voice: str
    options: Mapping[str, object]


@dataclasses.dataclass(frozen=True)
class VoiceProfile:
    profile_id: str
    display_name: str
    language: str
    providers: tuple[str, ...]


@dataclasses.dataclass(frozen=True)
class VoiceProfilesConfig:
    default_profile: str
    profiles: Mapping[str, VoiceProfile]
    providers: Mapping[str, ProviderConfig]

    def profile(self, profile_id: str | None = None) -> VoiceProfile:
        key = profile_id or self.default_profile
        if key not in self.profiles:
            raise ValueError(f"Unknown Ukrainian voice profile '{key}'. Available: {', '.join(self.profiles)}")
        return self.profiles[key]


def load_voice_profiles(config_path: Path | None = None) -> VoiceProfilesConfig:
    path = config_path or Path(__file__).with_name("voice_profiles.toml")
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    providers: dict[str, ProviderConfig] = {}
    for pid, spec in raw.get("providers", {}).items():
        opts = {k: v for k, v in spec.items() if k not in ("kind", "voice")}
        providers[pid] = ProviderConfig(provider_id=pid, kind=str(spec["kind"]), voice=str(spec["voice"]), options=opts)
    profiles: dict[str, VoiceProfile] = {}
    for prof_id, spec in raw.get("profiles", {}).items():
        profiles[prof_id] = VoiceProfile(
            profile_id=prof_id,
            display_name=str(spec.get("display_name", prof_id)),
            language=str(spec.get("language", "uk")),
            providers=tuple(str(p) for p in spec.get("providers", [])),
        )
    return VoiceProfilesConfig(
        default_profile=str(raw.get("default_profile", "tyshyn")),
        profiles=profiles,
        providers=providers,
    )


def convert_to_standard_wav(source_audio: Path, out_wav: Path, *, sample_rate: int = 24000) -> None:
    """Normalize any provider audio (WAV/MP3/etc.) to 24 kHz 16-bit mono PCM WAV for wave concat."""
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-v",
        "error",
        "-i",
        str(source_audio),
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


def _run_async[T](coroutine: Coroutine[Any, Any, T]) -> T:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coroutine)

    result: list[T] = []
    error: list[BaseException] = []

    def runner() -> None:
        try:
            result.append(asyncio.run(coroutine))
        except BaseException as exc:  # pragma: no cover - defensive thread boundary
            error.append(exc)

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    thread.join()
    if error:
        raise error[0]
    return result[0]


class StyleTTS2Provider:
    kind = "styletts2"

    def __init__(
        self,
        provider_id: str,
        voice: str,
        *,
        space: str,
        api_name: str = "/synthesize_multi",
        speed: float = 1.0,
    ) -> None:
        self.provider_id = provider_id
        self.voice = voice
        self.space = space
        self.api_name = api_name
        self.speed = speed
        self._client: Any = None

    @property
    def settings(self) -> Mapping[str, object]:
        return {"space": self.space, "api_name": self.api_name, "speed": self.speed}

    def _extract_audio_path(self, result: object) -> Path:
        if isinstance(result, (str, Path)):
            return Path(result)
        if isinstance(result, (list, tuple)):
            for item in result:
                try:
                    return self._extract_audio_path(item)
                except TypeError:
                    continue
        if isinstance(result, dict):
            for item in result.values():
                try:
                    return self._extract_audio_path(item)
                except TypeError:
                    continue
        raise TypeError(f"StyleTTS2 returned no audio path: {type(result).__name__}")

    def synthesize_wav(self, text: str, out_wav: Path) -> None:
        if self._client is None:
            from gradio_client import Client

            self._client = Client(self.space)
        result = self._client.predict(
            text=text,
            voice_audio=self.voice,
            speed=self.speed,
            api_name=self.api_name,
        )
        source = self._extract_audio_path(result)
        convert_to_standard_wav(source, out_wav)


class PiperProvider:
    kind = "piper"

    def __init__(self, provider_id: str, voice: str, *, model_path: Path, config_path: Path) -> None:
        self.provider_id = provider_id
        self.voice = voice
        self.model_path = model_path
        self.config_path = config_path
        self._voice_model: Any = None

    @property
    def settings(self) -> Mapping[str, object]:
        return {"model_path": self.model_path.as_posix(), "config_path": self.config_path.as_posix()}

    def synthesize_wav(self, text: str, out_wav: Path) -> None:
        if not self.model_path.is_file() or not self.config_path.is_file():
            raise FileNotFoundError(f"Piper model is unavailable: {self.model_path}")
        if self._voice_model is None:
            from piper.voice import PiperVoice  # ty: ignore[import-not-found]

            self._voice_model = PiperVoice.load(str(self.model_path), config_path=str(self.config_path))
        with tempfile.TemporaryDirectory() as tmpdir:
            raw_wav = Path(tmpdir) / "piper_raw.wav"
            with wave.open(str(raw_wav), "wb") as wf:
                self._voice_model.synthesize_wav(text, wf)
            convert_to_standard_wav(raw_wav, out_wav)


class EdgeTTSProvider:
    kind = "edge"

    def __init__(self, provider_id: str, voice: str, *, rate: str = "+0%") -> None:
        self.provider_id = provider_id
        self.voice = voice
        self.rate = rate

    @property
    def settings(self) -> Mapping[str, object]:
        return {"rate": self.rate}

    def synthesize_wav(self, text: str, out_wav: Path) -> None:
        import edge_tts

        with tempfile.TemporaryDirectory() as tmpdir:
            raw_mp3 = Path(tmpdir) / "edge_raw.mp3"
            communicate = edge_tts.Communicate(text, self.voice, rate=self.rate)
            _run_async(communicate.save(str(raw_mp3)))
            convert_to_standard_wav(raw_mp3, out_wav)


def build_ukrainian_providers(
    project_root: Path,
    *,
    profile_id: str | None = None,
    config_path: Path | None = None,
) -> tuple[VoiceProfile, list[UkrainianVoiceProvider]]:
    config = load_voice_profiles(config_path)
    profile = config.profile(profile_id)
    providers: list[UkrainianVoiceProvider] = []
    for pid in profile.providers:
        cfg = config.providers[pid]
        opts = cfg.options
        if cfg.kind == "styletts2":
            providers.append(
                StyleTTS2Provider(
                    cfg.provider_id,
                    cfg.voice,
                    space=str(opts["space"]),
                    api_name=str(opts.get("api_name", "/synthesize_multi")),
                    speed=float(str(opts.get("speed", 1.0))),
                )
            )
        elif cfg.kind == "piper":
            providers.append(
                PiperProvider(
                    cfg.provider_id,
                    cfg.voice,
                    model_path=project_root / str(opts["model_path"]),
                    config_path=project_root / str(opts["config_path"]),
                )
            )
        elif cfg.kind == "edge":
            providers.append(EdgeTTSProvider(cfg.provider_id, cfg.voice, rate=str(opts.get("rate", "+0%"))))
        else:
            raise ValueError(f"Unsupported Ukrainian voice provider kind: {cfg.kind}")
    return profile, providers


class UkrainianFallbackTTS:
    """Selects the first available Ukrainian provider and pins it for the entire topic batch."""

    def __init__(self, providers: list[UkrainianVoiceProvider], *, profile_id: str = "tyshyn") -> None:
        if not providers:
            raise ValueError("At least one Ukrainian TTS provider is required")
        self.providers = providers
        self.profile_id = profile_id
        self.pinned_provider: UkrainianVoiceProvider | None = None
        self.fallback_reasons: list[str] = []

    def synthesize(self, text: str, out_wav: Path) -> tuple[str, str]:
        """Synthesize text into a 24 kHz mono PCM WAV and return (provider_id, voice)."""
        if self.pinned_provider is not None:
            self.pinned_provider.synthesize_wav(text, out_wav)
            return self.pinned_provider.provider_id, self.pinned_provider.voice

        errors: list[str] = []
        for provider in self.providers:
            try:
                with tempfile.TemporaryDirectory() as tmpdir:
                    candidate = Path(tmpdir) / "clip.wav"
                    provider.synthesize_wav(text, candidate)
                    out_wav.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(candidate, out_wav)
                self.pinned_provider = provider
                return provider.provider_id, provider.voice
            except Exception as error:
                reason = f"{provider.provider_id}: {type(error).__name__}: {error}"
                errors.append(reason)
                self.fallback_reasons.append(reason)
        raise RuntimeError("All Ukrainian TTS providers failed: " + "; ".join(errors))
