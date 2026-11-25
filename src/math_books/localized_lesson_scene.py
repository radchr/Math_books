"""Shared scene for future lessons; translated text is loaded before layout."""

import json
import os
import re
import textwrap
from pathlib import Path

from manim import DOWN, UP, FadeIn, FadeOut, Group, MathTex, Text

from math_books.cue_timeline import event_timeline, validate_event_log
from math_books.languages import validate_language
from math_books.lessons import load_lesson
from math_books.video_ui import ACCENT_GOLD, FONT, VerticalShortScene, configure_vertical_9_16

configure_vertical_9_16()


class LocalizedLessonScene(VerticalShortScene):
    def construct(self) -> None:
        path = Path(os.environ["MATH_BOOKS_LESSON_PATH"]).resolve()
        language = validate_language(os.environ.get("MATH_BOOKS_LANGUAGE", "ru"))
        root = path.parents[2]
        self._lesson_language = language
        snapshot_path = os.environ.get("MATH_BOOKS_TIMING_SNAPSHOT_PATH")
        self._timing_snapshot = json.loads(Path(snapshot_path).read_text(encoding="utf-8")) if snapshot_path else {}
        self._lesson_rows = load_lesson(root, path.stem, language)
        self._manifest_path = Path(os.environ["MATH_BOOKS_MANIFEST_PATH"])
        manifest = json.loads(self._manifest_path.read_text(encoding="utf-8"))
        if any(item.get("language") != language for item in manifest):
            raise ValueError("Render manifest language differs from lesson")
        self._manifest_items = {item["id"]: item for item in manifest}
        if [s["id"] for s in self._lesson_rows] != [s["id"] for s in manifest]:
            raise ValueError("Render scene IDs differ from lesson")
        expected_events = event_timeline(self._lesson_rows, manifest, self._timing_snapshot, language)
        events_path = os.environ.get("MATH_BOOKS_EVENT_TIMELINE_PATH")
        self._event_timeline = (
            json.loads(Path(events_path).read_text(encoding="utf-8")) if events_path else expected_events
        )
        if self._event_timeline != expected_events:
            raise ValueError("Render cue inputs differ from the verified snapshot")
        self._event_records = []
        audio_offset = 0.0
        for index, row in enumerate(self._lesson_rows):
            duration = float(self._manifest_items[row["id"]]["duration"])
            start_frame = round(audio_offset * 30)
            end_frame = round((audio_offset + duration) * 30)
            if round(self.renderer.time * 30) != start_frame:
                raise ValueError("Rendered scene start differs from the cumulative audio clock")
            self.run_segment(lambda value, row=row: self.show_card(row, value), (end_frame - start_frame) / 30)
            if index < len(self._lesson_rows) - 1:
                self.play(FadeOut(Group(*self.mobjects)), run_time=0.4)
            else:
                self.wait((9 + 0.001) / 30)
            audio_offset += duration + 0.4
        validate_event_log(self._event_timeline, self._event_records)
        log_path = os.environ.get("MATH_BOOKS_EVENT_LOG_PATH")
        if log_path:
            Path(log_path).write_text(json.dumps(self._event_records), encoding="utf-8")

    def _pad(self, target_dur: float, spent: float | None = None) -> None:
        """Round cumulative endpoints; avoid truncating floating-point frozen waits."""
        VerticalShortScene.check_frame_bounds(self)
        target_frames = round(target_dur * 30)
        elapsed_frames = round((self.renderer.time - self._segment_start) * 30)
        remaining = target_frames - elapsed_frames
        if remaining < 0:
            raise ValueError("Scene animations exceed their allocated video frames")
        if remaining:
            self.wait((remaining + 0.001) / 30)
        if round((self.renderer.time - self._segment_start) * 30) != target_frames:
            raise ValueError("Renderer did not reach the allocated audio endpoint")

    def word_timestamp(
        self, scene_id: str, target_word: str, *, fallback: float | None = None, after_s: float = 0.0
    ) -> float | None:
        def token(word: str) -> str:
            return "".join(re.findall(r"[^\W\d_]+", word.casefold().replace("ё", "е")))

        target = token(target_word)
        for word in getattr(self, "_timing_snapshot", {}).get(scene_id, []):
            if target and token(word["word"]) == target and word["start"] >= after_s:
                return float(word["start"])
        return fallback

    def show_card(self, row: dict, duration: float) -> None:
        title = Text(row["title"], font=FONT, font_size=40, color=ACCENT_GOLD)
        if title.width > 7.6:
            title.scale_to_fit_width(7.6)
        title.move_to(UP * 5.7)
        wrapped = "\n".join(
            line for paragraph in row["body"].splitlines() for line in (textwrap.wrap(paragraph, width=34) or [""])
        )
        body = Text(wrapped, font=FONT, font_size=36, line_spacing=1.3)
        if body.width > 7.4:
            body.scale_to_fit_width(7.4)
        if body.height > 4.8:
            body.scale_to_fit_height(4.8)
        body.move_to(UP * 1.7)
        objects = {"title": title, "body": body}
        if row["formula"]:
            formula = MathTex(row["formula"], font_size=48)
            if formula.width > 7.4:
                formula.scale_to_fit_width(7.4)
            formula.move_to(DOWN * 2.1)
            objects["formula"] = formula
        # Bound the animation cost for short test clips; narration remains authoritative.
        events = self._event_timeline[row["id"]]
        hidden = {event["target"] for event in events}
        visible = [mob for name, mob in objects.items() if name not in hidden]
        initial_duration = min(0.6, duration / 2, events[0]["time"] if events else duration)
        if visible and initial_duration >= 1 / 30:
            self.play(*[FadeIn(mob) for mob in visible], run_time=initial_duration)
        else:
            self.add(*visible)
        for event in events:
            remaining = event["time"] - (self.renderer.time - self._segment_start)
            if remaining >= 1 / 30 - 1e-8:
                self.wait((round(remaining * 30) + 0.001) / 30)
            self.add(objects[event["target"]])
            self._event_records.append(
                {
                    "scene_id": row["id"],
                    "id": event["id"],
                    "target": event["target"],
                    "frame": round((self.renderer.time - self._segment_start) * 30),
                    "global_frame": round(self.renderer.time * 30),
                }
            )
        self._pad(duration)
