"""Multi-provider Ukrainian TTS fallback chain (StyleTTS2 -> Piper -> Edge TTS) with voice pinning.

Adapted from radchr/Anime (NauKadr) and standardized to 24 kHz mono 16-bit PCM WAV so clips plug
directly into Math_books' lossless stdlib `wave` concatenation and local ASR QA pipeline.
"""

from __future__ import annotations

import asyncio
import dataclasses
import hashlib
import json
import shutil
import subprocess
import tempfile
import threading
import tomllib
import wave
from collections.abc import Callable, Coroutine, Mapping
from pathlib import Path
from typing import Any, Protocol

from math_books.pipeline_errors import RecognitionError, ReviewRequiredError


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
        if isinstance(result, dict):
            path_val = result.get("path")
            if isinstance(path_val, (str, Path)):
                return Path(path_val)
            candidates: list[Path] = []
            for item in result.values():
                try:
                    candidates.append(self._extract_audio_path(item))
                except TypeError:
                    continue
            for candidate in candidates:
                if candidate.is_file():
                    return candidate
            if candidates:
                return candidates[0]
        if isinstance(result, (list, tuple)):
            candidates = []
            for item in result:
                try:
                    candidates.append(self._extract_audio_path(item))
                except TypeError:
                    continue
            for candidate in candidates:
                if candidate.is_file():
                    return candidate
            if candidates:
                return candidates[0]
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

    def __init__(
        self,
        provider_id: str,
        voice: str,
        *,
        model_path: Path,
        config_path: Path,
        model_spec: str | None = None,
        config_spec: str | None = None,
    ) -> None:
        self.provider_id = provider_id
        self.voice = voice
        self.model_path = model_path
        self.config_path = config_path
        self.model_spec = model_spec or model_path.as_posix()
        self.config_spec = config_spec or config_path.as_posix()
        self._voice_model: Any = None

    @property
    def settings(self) -> Mapping[str, object]:
        return {"model_path": self.model_spec, "config_path": self.config_spec}

    @property
    def resolved_paths(self) -> Mapping[str, Path]:
        return {"model_path": self.model_path, "config_path": self.config_path}

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
        return {"rate": self.rate, "boundary": "WordBoundary"}

    def synthesize_wav(self, text: str, out_wav: Path) -> None:
        import edge_tts

        with tempfile.TemporaryDirectory() as tmpdir:
            raw_mp3 = Path(tmpdir) / "edge_raw.mp3"
            metadata = Path(tmpdir) / "edge_metadata.jsonl"
            communicate = edge_tts.Communicate(text, self.voice, rate=self.rate, boundary="WordBoundary")
            _run_async(communicate.save(str(raw_mp3), str(metadata)))
            convert_to_standard_wav(raw_mp3, out_wav)
            with wave.open(str(out_wav), "rb") as wav:
                sample_rate = wav.getframerate()
            checksum = hashlib.sha256(out_wav.read_bytes()).hexdigest()
            evidence = {
                "schema_version": 1,
                "provider": self.provider_id,
                "advisory": True,
                "clock_source": "edge_word_boundary_ticks_before_mp3_decode",
                "ticks_per_second": 10_000_000,
                "uncertainty": "MP3 encoder/decoder delay is unmeasured; provider ticks are not decoded WAV timestamps",
                "conversion": "ffmpeg decode/resample to 24000 Hz mono PCM16; no explicit delay correction",
                "source_audio_sha256": hashlib.sha256(raw_mp3.read_bytes()).hexdigest(),
                "decoded_wav_sha256": checksum,
                "wav_sha256": checksum,
                "sample_rate": sample_rate,
                "trim_start_samples": 0,
                "raw_metadata": metadata.read_text(encoding="utf-8"),
            }
            _validate_timing_evidence(evidence)
            timing_sidecar(out_wav).write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")


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
            model_rel = str(opts["model_path"])
            config_rel = str(opts["config_path"])
            providers.append(
                PiperProvider(
                    cfg.provider_id,
                    cfg.voice,
                    model_path=project_root / model_rel,
                    config_path=project_root / config_rel,
                    model_spec=model_rel,
                    config_spec=config_rel,
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

    def pin(self, provider_id: str, voice: str) -> None:
        """Restore a verified cached identity before generating missing clips."""
        matching = next((p for p in self.providers if (p.provider_id, p.voice) == (provider_id, voice)), None)
        if matching is None:
            raise ValueError("Cached Ukrainian voice is unavailable in the current profile")
        if self.pinned_provider is not None and self.pinned_provider is not matching:
            raise ValueError("Cached Ukrainian clips mix provider/voice identities")
        self.pinned_provider = matching

    def synthesize(
        self, text: str, out_wav: Path, *, validate: Callable[[Path], None] | None = None
    ) -> tuple[str, str]:
        """Synthesize text into a 24 kHz mono PCM WAV and return (provider_id, voice)."""
        if self.pinned_provider is not None:
            self.pinned_provider.synthesize_wav(text, out_wav)
            if validate is not None:
                validate(out_wav)
            return self.pinned_provider.provider_id, self.pinned_provider.voice

        errors: list[str] = []
        for provider in self.providers:
            try:
                with tempfile.TemporaryDirectory() as tmpdir:
                    candidate = Path(tmpdir) / "clip.wav"
                    provider.synthesize_wav(text, candidate)
                    if validate is not None:
                        validate(candidate)
                    out_wav.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(candidate, out_wav)
                    if timing_sidecar(candidate).is_file():
                        shutil.copy2(timing_sidecar(candidate), timing_sidecar(out_wav))
                self.pinned_provider = provider
                return provider.provider_id, provider.voice
            except (RecognitionError, ReviewRequiredError):
                raise
            except Exception as error:
                reason = f"{provider.provider_id}: {type(error).__name__}: {error}"
                errors.append(reason)
                self.fallback_reasons.append(reason)
        raise RuntimeError("All Ukrainian TTS providers failed: " + "; ".join(errors))


def timing_sidecar(wav_path: Path) -> Path:
    return wav_path.with_suffix(".provider-timings.json")


def _validate_timing_evidence(evidence: dict) -> None:
    if (
        evidence.get("schema_version") != 1
        or evidence.get("advisory") is not True
        or evidence.get("clock_source") != "edge_word_boundary_ticks_before_mp3_decode"
        or evidence.get("ticks_per_second") != 10_000_000
        or not isinstance(evidence.get("uncertainty"), str)
        or not evidence["uncertainty"]
        or type(evidence.get("sample_rate")) is not int
        or evidence["sample_rate"] <= 0
        or type(evidence.get("trim_start_samples")) is not int
        or evidence["trim_start_samples"] < 0
    ):
        raise ValueError("Malformed advisory provider timing clock")
    for key in ("source_audio_sha256", "decoded_wav_sha256", "wav_sha256"):
        value = evidence.get(key)
        if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            raise ValueError("Malformed provider timing audio identity")
    try:
        entries = [json.loads(line) for line in evidence["raw_metadata"].splitlines() if line.strip()]
        words = [entry for entry in entries if entry["type"] == "WordBoundary"]
        if not words:
            raise ValueError("Missing WordBoundary metadata")
        for entry in words:
            if (
                type(entry["offset"]) is not int
                or entry["offset"] < 0
                or type(entry["duration"]) is not int
                or entry["duration"] < 0
                or not isinstance(entry["text"], str)
                or not entry["text"].strip()
            ):
                raise ValueError("Malformed WordBoundary metadata")
    except (KeyError, TypeError, AttributeError, json.JSONDecodeError) as error:
        raise ValueError("Malformed raw provider timing metadata") from error


def validate_provider_timings(item: Mapping[str, object], audio_dir: Path) -> dict | None:
    """Validate advisory evidence identity; this does not certify word alignment or content."""
    if not item.get("provider_timings"):
        if item.get("timing_required"):
            raise ValueError("Missing required advisory provider timings")
        return None
    try:
        path = (audio_dir / str(item["provider_timings"])).resolve()
        wav = (audio_dir / str(item["wav"])).resolve()
        if not path.is_relative_to(audio_dir.resolve()) or not wav.is_relative_to(audio_dir.resolve()):
            raise ValueError("Provider timing path escapes audio directory")
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != item["provider_timings_sha256"]:
            raise ValueError("Provider timing checksum mismatch")
        evidence = json.loads(raw)
        _validate_timing_evidence(evidence)
        checksum = hashlib.sha256(wav.read_bytes()).hexdigest()
        if evidence["wav_sha256"] != checksum or item["wav_sha256"] != checksum:
            raise ValueError("Provider timing WAV identity mismatch")
        with wave.open(str(wav), "rb") as pcm:
            if pcm.getframerate() != evidence["sample_rate"]:
                raise ValueError("Provider timing sample clock mismatch")
        return evidence
    except (OSError, KeyError, TypeError, AttributeError, wave.Error) as error:
        raise ValueError("Missing or malformed advisory provider timing evidence") from error


def profile_fingerprint(profile: VoiceProfile, providers: list[UkrainianVoiceProvider]) -> str:
    """Bind caches to provider settings and local model/config contents."""
    identities = []
    for provider in providers:
        settings = dict(provider.settings)
        resolved_map = getattr(provider, "resolved_paths", {})
        files = {}
        for key, value in settings.items():
            if key.endswith("_path") and isinstance(value, (str, Path)):
                path = Path(resolved_map[key]) if key in resolved_map else Path(value)
                if path.is_file():
                    digest = hashlib.sha256()
                    with path.open("rb") as source:
                        for chunk in iter(lambda: source.read(1024 * 1024), b""):
                            digest.update(chunk)
                    files[key] = digest.hexdigest()
                else:
                    files[key] = None
        identities.append(
            {
                "id": provider.provider_id,
                "voice": provider.voice,
                "kind": provider.kind,
                "settings": settings,
                "files": files,
            }
        )
    payload = {"profile": dataclasses.asdict(profile), "providers": identities}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
