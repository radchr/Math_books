"""Topic metadata and content discovery, independent of synthesis and rendering."""

from __future__ import annotations

import dataclasses
import importlib
from pathlib import Path

from math_books.languages import validate_language
from math_books.lessons import discover_lessons, lesson_path, load_lesson


@dataclasses.dataclass(frozen=True)
class VideoTopic:
    key: str
    video_dir: str
    scene_file: str
    scene_class: str
    output_name: str
    tts_module: str
    language: str = "ru"
    lesson_file: str | None = None


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


def get_topic(key: str, language: str = "ru", root: Path | None = None) -> VideoTopic:
    validate_language(language)
    base = root or project_root()
    if key in VIDEO_TOPICS:
        if language != "ru":
            raise ValueError(f"Legacy topic {key!r} has no {language} translation; create a new lesson")
        return VIDEO_TOPICS[key]
    path = lesson_path(base, key)
    if not path.is_file():
        raise ValueError(f"Unknown topic {key!r}; add content/lessons/{key}.json")
    load_lesson(base, key, language)
    return VideoTopic(
        key,
        f"videos/video_{key}/{language}",
        "src/math_books/localized_lesson_scene.py",
        "LocalizedLessonScene",
        f"{key}.mp4",
        "",
        language,
        str(path.relative_to(base)),
    )


def available_topics(root: Path, language: str = "ru") -> dict[str, VideoTopic]:
    validate_language(language)
    topics = dict(VIDEO_TOPICS) if language == "ru" else {}
    for key in discover_lessons(root):
        if key in VIDEO_TOPICS:
            raise ValueError(f"New lesson collides with legacy topic: {key}")
        topics[key] = get_topic(key, language, root)
    return topics


def topic_scenes(topic: VideoTopic, base: Path) -> list[dict]:
    if topic.lesson_file is not None:
        return load_lesson(base, topic.key, topic.language)
    return importlib.import_module(topic.tts_module).SCENES
