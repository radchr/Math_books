"""Shared scene for future lessons; translated text is loaded before layout."""

import json
import os
from fractions import Fraction
from pathlib import Path

from manim import (
    DOWN,
    UP,
    Circumscribe,
    FadeIn,
    FadeOut,
    Group,
    GrowFromEdge,
    Indicate,
    LaggedStart,
    MathTex,
    ReplacementTransform,
    TransformMatchingTex,
    Write,
)

from math_books.cue_timeline import event_timeline, timed_event_timeline, validate_event_log
from math_books.languages import validate_language
from math_books.lessons import load_lesson
from math_books.themes import get_theme
from math_books.video_ui import (
    DEFAULT_ALLOWED_OVERLAP_PAIRS,
    VerticalShortScene,
    configure_vertical_9_16,
    require_no_mobject_overlaps,
)
from math_books.visual_blocks import get_visual_block

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
        music_only = self._lesson_rows[0].get("audio_mode") == "music_only"
        if music_only:
            durations = {row["id"]: float(row["duration_s"]) for row in self._lesson_rows}
            expected_events = timed_event_timeline(self._lesson_rows)
        else:
            self._manifest_path = Path(os.environ["MATH_BOOKS_MANIFEST_PATH"])
            manifest = json.loads(self._manifest_path.read_text(encoding="utf-8"))
            if any(item.get("language") != language for item in manifest):
                raise ValueError("Render manifest language differs from lesson")
            self._manifest_items = {item["id"]: item for item in manifest}
            if [s["id"] for s in self._lesson_rows] != [s["id"] for s in manifest]:
                raise ValueError("Render scene IDs differ from lesson")
            durations = {item["id"]: float(item["duration"]) for item in manifest}
            expected_events = event_timeline(self._lesson_rows, manifest, self._timing_snapshot, language)
        events_path = os.environ.get("MATH_BOOKS_EVENT_TIMELINE_PATH")
        self._event_timeline = (
            json.loads(Path(events_path).read_text(encoding="utf-8")) if events_path else expected_events
        )
        if self._event_timeline != expected_events:
            raise ValueError("Render cue inputs differ from the verified snapshot")
        self._event_records = []
        audio_offset = Fraction(0)
        pause_duration = Fraction(2, 5)
        for index, row in enumerate(self._lesson_rows):
            duration = durations[row["id"]]
            duration_exact = Fraction(str(duration))
            start_frame = round(audio_offset * 30)
            end_frame = round((audio_offset + duration_exact) * 30)
            if round(self.renderer.time * 30) != start_frame:
                raise ValueError("Rendered scene start differs from the cumulative audio clock")
            self.run_segment(lambda value, row=row: self.show_card(row, value), (end_frame - start_frame) / 30)
            if index < len(self._lesson_rows) - 1:
                self.play(FadeOut(Group(*self.mobjects)), run_time=0.4)
            else:
                self.wait((9 + 0.001) / 30)
            audio_offset += duration_exact + pause_duration
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

    def show_card(self, row: dict, duration: float) -> None:
        theme = get_theme(row.get("theme", "basketball_dark"))
        self.camera.background_color = theme.bg  # ty: ignore[invalid-assignment]
        template = row.get("visual", {}).get("template", "text_card")
        spec = get_visual_block(template)
        objects = spec.build(theme, self._lesson_language, row)
        require_no_mobject_overlaps(objects, allowed_pairs=DEFAULT_ALLOWED_OVERLAP_PAIRS | spec.allowed_overlap_pairs)
        # Bound the animation cost for short test clips; narration remains authoritative.
        events = self._event_timeline[row["id"]]
        for event in events:
            if event["target"] not in objects:
                raise ValueError(f"Cue {event['id']} target {event['target']!r} not produced by {template!r}")
        hidden = {event["target"] for event in events if event.get("action", "reveal") == "reveal"}
        if template == "equation_morph":
            # Subsequent morph states replace step_1 in place; never stack them simultaneously at t=0.
            for name in objects:
                if name.startswith("step_") and name != "step_1":
                    hidden.add(name)
        visible = [mob for name, mob in objects.items() if name not in hidden]
        active_morph_step: str | None = (
            "step_1" if template == "equation_morph" and "step_1" in objects and "step_1" not in hidden else None
        )
        initial_duration = min(0.6, duration / 2, events[0]["time"] if events else duration)
        initial_frames = int(initial_duration * 30)
        if visible and initial_frames >= 2:
            self.play(
                LaggedStart(*[FadeIn(mob, shift=UP * 0.2) for mob in visible], lag_ratio=0.15),
                run_time=initial_frames / 30,
            )
        else:
            self.add(*visible)
        for idx, event in enumerate(events):
            remaining = event["time"] - (self.renderer.time - self._segment_start)
            if remaining >= 1 / 30 - 1e-8:
                self.wait((round(remaining * 30) + 0.001) / 30)
            self._event_records.append(
                {
                    "scene_id": row["id"],
                    "id": event["id"],
                    "target": event["target"],
                    "frame": round((self.renderer.time - self._segment_start) * 30),
                    "global_frame": round(self.renderer.time * 30),
                }
            )
            target = event["target"]
            action = event.get("action", "reveal")
            mob = objects[target]
            next_boundary = events[idx + 1]["time"] if idx + 1 < len(events) else duration
            budget_s = next_boundary - (self.renderer.time - self._segment_start)
            max_anim_frames = 15 if (template == "equation_morph" and target.startswith("step_")) else 12
            anim_frames = min(max_anim_frames, max(0, int(budget_s * 30) - 1))
            if action == "indicate":
                if anim_frames >= 2:
                    self.play(Indicate(mob, color=theme.secondary, scale_factor=1.08), run_time=anim_frames / 30)
                continue
            if action == "circumscribe":
                if anim_frames >= 2:
                    self.play(Circumscribe(mob, color=theme.secondary), run_time=anim_frames / 30)
                continue
            if template == "equation_morph" and target.startswith("step_") and active_morph_step is not None:
                prev_grp = objects[active_morph_step]
                prev_tex = prev_grp[1] if len(prev_grp) > 1 and isinstance(prev_grp[1], MathTex) else None
                next_tex = mob[1] if len(mob) > 1 and isinstance(mob[1], MathTex) else None
                if anim_frames >= 3 and prev_tex is not None and next_tex is not None:
                    anims = [
                        ReplacementTransform(prev_grp[0], mob[0]),
                        TransformMatchingTex(prev_tex, next_tex),
                    ]
                    if len(prev_grp) > 2:
                        anims.append(FadeOut(prev_grp[2]))
                    if len(mob) > 2:
                        anims.append(FadeIn(mob[2], shift=UP * 0.15))
                    self.play(*anims, run_time=anim_frames / 30)
                    self.remove(prev_grp)
                    self.add(mob)
                else:
                    self.remove(prev_grp)
                    self.add(mob)
                active_morph_step = target
            else:
                if anim_frames >= 2:
                    if target == "formula" or isinstance(mob, MathTex):
                        self.play(Write(mob), run_time=anim_frames / 30)
                    elif target.startswith("bar_"):
                        self.play(GrowFromEdge(mob, DOWN), run_time=anim_frames / 30)
                    else:
                        self.play(FadeIn(mob, shift=UP * 0.25), run_time=anim_frames / 30)
                else:
                    self.add(mob)
                if template == "equation_morph" and target.startswith("step_"):
                    active_morph_step = target
        self._pad(duration)
