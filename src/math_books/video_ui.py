"""Shared 9:16 vertical Manim canvas config, theme palette, and reusable UI components."""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

import numpy as np
from manim import (
    DOWN,
    GRAY_B,
    LEFT,
    RED_C,
    RIGHT,
    UP,
    WHITE,
    Arc,
    Circle,
    Line,
    Rectangle,
    RoundedRectangle,
    Scene,
    Text,
    VGroup,
    config,
)

FONT = "DejaVu Sans"
BG_COLOR = "#0D1B2A"
ACCENT_ORANGE = "#FF6B1A"
ACCENT_CYAN = "#00D4FF"
ACCENT_GOLD = "#FFD166"
ACCENT_MINT = "#2EC4B6"
CARD_BG = "#1B263B"


def configure_vertical_9_16() -> None:
    """Configure Manim for 1080x1920 (9:16) 30 fps vertical shorts."""
    config.pixel_width = 1080
    config.pixel_height = 1920
    config.frame_width = 9.0
    config.frame_height = 16.0
    config.frame_rate = 30
    config.background_color = BG_COLOR


def make_badge(label: str, color: str = ACCENT_ORANGE) -> VGroup:
    """Create a clean top pill badge fitted safely inside the 9:16 frame."""
    txt = Text(label, font=FONT, font_size=34, weight="BOLD", color=WHITE)
    if txt.width > 7.2:
        txt.scale_to_fit_width(7.2)
    box = RoundedRectangle(
        corner_radius=0.25,
        width=max(txt.width + 0.9, 4.2),
        height=txt.height + 0.45,
        fill_color=color,
        fill_opacity=0.95,
        stroke_width=0,
    )
    txt.move_to(box.get_center())
    grp = VGroup(box, txt)
    grp.move_to(UP * 6.5)
    return grp


def make_subtitle(text: str, y: float = 5.2, color: str = ACCENT_GOLD) -> Text:
    """Create a fitted section subtitle."""
    txt = Text(text, font=FONT, font_size=36, weight="BOLD", color=color)
    if txt.width > 7.8:
        txt.scale_to_fit_width(7.8)
    txt.move_to(UP * y)
    return txt


def make_caption(text: str, y: float = -5.4, color: str = WHITE) -> VGroup:
    """Create a bottom caption card fitted safely inside the frame."""
    txt = Text(text, font=FONT, font_size=32, color=color, line_spacing=1.2)
    if txt.width > 7.6:
        txt.scale_to_fit_width(7.6)
    box = RoundedRectangle(
        corner_radius=0.25,
        width=txt.width + 0.8,
        height=txt.height + 0.55,
        fill_color=CARD_BG,
        fill_opacity=0.92,
        stroke_color=ACCENT_ORANGE,
        stroke_width=2.5,
    )
    txt.move_to(box.get_center())
    grp = VGroup(box, txt)
    grp.move_to(UP * y)
    return grp


def make_basketball(radius: float = 0.42) -> VGroup:
    """Create a stylized basketball icon."""
    ball = Circle(
        radius=radius,
        fill_color=ACCENT_ORANGE,
        fill_opacity=1.0,
        stroke_color="#220F00",
        stroke_width=3,
    )
    h_line = Line(LEFT * radius, RIGHT * radius, color="#220F00", stroke_width=2.5)
    v_line = Line(DOWN * radius, UP * radius, color="#220F00", stroke_width=2.5)
    arc1 = Arc(radius=radius * 0.72, start_angle=-0.9, angle=1.8, color="#220F00", stroke_width=2.5).shift(
        LEFT * radius * 0.65
    )
    arc2 = Arc(radius=radius * 0.72, start_angle=np.pi - 0.9, angle=1.8, color="#220F00", stroke_width=2.5).shift(
        RIGHT * radius * 0.65
    )
    return VGroup(ball, h_line, v_line, arc1, arc2)


def make_half_court(center_y: float = 0.8) -> VGroup:
    """Create a clean top-down half-court diagram."""
    court = Rectangle(
        width=7.4,
        height=6.4,
        stroke_color="#415A77",
        stroke_width=3,
        fill_color="#14243B",
        fill_opacity=0.7,
    )
    court.move_to(UP * center_y)
    top_y = court.get_top()[1]
    paint = Rectangle(width=2.6, height=2.6, stroke_color="#415A77", stroke_width=2.5)
    paint.move_to([0, top_y - 1.3, 0])
    three_arc = Arc(radius=3.1, start_angle=-np.pi, angle=np.pi, color="#415A77", stroke_width=2.5)
    three_arc.move_arc_center_to([0, top_y - 0.55, 0])
    backboard = Line(LEFT * 0.8, RIGHT * 0.8, color=WHITE, stroke_width=5).move_to([0, top_y - 0.28, 0])
    rim = Circle(radius=0.2, color=ACCENT_ORANGE, stroke_width=4).move_to([0, top_y - 0.55, 0])
    return VGroup(court, paint, three_arc, backboard, rim)


def make_scoreboard(score_str: str, label: str = "ТАБЛО", y: float = 1.6) -> VGroup:
    """Create a glowing digital-style scoreboard card."""
    box = RoundedRectangle(
        corner_radius=0.3,
        width=4.4,
        height=2.3,
        fill_color="#09111E",
        fill_opacity=0.98,
        stroke_color=ACCENT_ORANGE,
        stroke_width=4,
    )
    lbl = Text(label, font=FONT, font_size=26, weight="BOLD", color=GRAY_B).move_to(box.get_top() + DOWN * 0.42)
    num = Text(score_str, font=FONT, font_size=82, weight="BOLD", color=ACCENT_GOLD).move_to(
        box.get_center() + DOWN * 0.18
    )
    return VGroup(box, lbl, num).move_to(UP * y)


def make_stat_card(
    title: str,
    left_txt: str,
    right_txt: str,
    y: float,
    highlight_left: bool = True,
) -> VGroup:
    """Create a sleek two-player comparison card."""
    box = RoundedRectangle(
        corner_radius=0.25,
        width=7.8,
        height=2.2,
        fill_color=CARD_BG,
        fill_opacity=0.95,
        stroke_color=ACCENT_CYAN,
        stroke_width=2.5,
    ).move_to(UP * y)
    hdr = Text(title, font=FONT, font_size=26, weight="BOLD", color=ACCENT_GOLD).move_to(box.get_top() + DOWN * 0.42)
    l_col = ACCENT_MINT if highlight_left else RED_C
    r_col = RED_C if highlight_left else ACCENT_MINT
    l_mob = Text(left_txt, font=FONT, font_size=34, weight="BOLD", color=l_col).move_to(
        box.get_center() + LEFT * 1.9 + DOWN * 0.25
    )
    r_mob = Text(right_txt, font=FONT, font_size=34, weight="BOLD", color=r_col).move_to(
        box.get_center() + RIGHT * 1.9 + DOWN * 0.25
    )
    sep = Line(
        box.get_center() + UP * 0.15,
        box.get_center() + DOWN * 0.75,
        color=GRAY_B,
        stroke_width=2,
    )
    return VGroup(box, hdr, l_mob, r_mob, sep)


class VerticalShortScene(Scene):
    """Base Manim Scene for silent 9:16 vertical shorts synced via audio manifest."""

    SAFE_MAX_ABS_X = 4.35
    SAFE_MIN_Y = -6.15
    SAFE_MAX_Y = 7.45

    def _resolve_manifest_path(self, video_dir_name: str) -> Path:
        override = os.environ.get("MATH_BOOKS_MANIFEST_PATH")
        if override:
            return Path(override)
        root = Path(__file__).resolve().parents[2]
        from math_books.video_builder import VIDEO_TOPICS

        topic = next(
            (
                item
                for item in VIDEO_TOPICS.values()
                if item.video_dir == video_dir_name or Path(item.video_dir).name == Path(video_dir_name).name
            ),
            None,
        )
        rel_dir = topic.video_dir if topic is not None else video_dir_name
        return root / rel_dir / "audio" / "manifest.json"

    def _load_durations(self, video_dir_name: str) -> dict[str, float]:
        self._manifest_path = self._resolve_manifest_path(video_dir_name)
        manifest = json.loads(self._manifest_path.read_text(encoding="utf-8"))
        self._manifest_items = {item["id"]: item for item in manifest}
        return {item["id"]: float(item["duration"]) for item in manifest}

    def word_timestamp(
        self,
        scene_id: str,
        target_word: str,
        *,
        fallback: float | None = None,
        after_s: float = 0.0,
    ) -> float | None:
        """Look up the spoken start timestamp (in seconds) of `target_word` from the cached ASR QA receipt."""
        manifest_path = getattr(self, "_manifest_path", None)
        items = getattr(self, "_manifest_items", None)
        if manifest_path is None or not items or scene_id not in items:
            return fallback
        item = items[scene_id]
        qa_dir = manifest_path.parent / "qa"
        if not qa_dir.is_dir():
            return fallback
        wav_sha = item.get("wav_sha256")
        if not wav_sha:
            wav_file = manifest_path.parent / item["wav"]
            if not wav_file.is_file():
                return fallback
            wav_sha = hashlib.sha256(wav_file.read_bytes()).hexdigest()
        text_sha_prefix = hashlib.sha256(item.get("text", "").encode("utf-8")).hexdigest()[:16]
        candidates = sorted(
            qa_dir.glob(f"{wav_sha}-{text_sha_prefix}-*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not candidates:
            return fallback
        try:
            receipt = json.loads(candidates[0].read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return fallback
        norm_target = re.sub(r"[^а-яa-z0-9]+", "", target_word.lower().replace("ё", "е"))
        if not norm_target:
            return fallback
        for segment in receipt.get("segments", []):
            for word_obj in segment.get("words", []):
                raw_w = str(word_obj.get("word", "")).lower().replace("ё", "е")
                clean_w = re.sub(r"[^а-яa-z0-9]+", "", raw_w)
                start_t = float(word_obj.get("start", 0.0))
                if start_t >= after_s and (clean_w == norm_target or clean_w.startswith(norm_target)):
                    return start_t
        return fallback

    def check_frame_bounds(
        self,
        *,
        max_abs_x: float = SAFE_MAX_ABS_X,
        min_y: float = SAFE_MIN_Y,
        max_y: float = SAFE_MAX_Y,
    ) -> None:
        """Verify that all on-screen mobjects fit within the 9:16 vertical safe area."""
        for mob in getattr(self, "mobjects", []):
            if getattr(mob, "width", 0) <= 0 or getattr(mob, "height", 0) <= 0:
                continue
            left_x = float(mob.get_left()[0])
            right_x = float(mob.get_right()[0])
            bottom_y = float(mob.get_bottom()[1])
            top_y = float(mob.get_top()[1])
            if left_x < -max_abs_x or right_x > max_abs_x:
                raise ValueError(
                    f"Mobject {mob!r} exceeds horizontal 9:16 safe bounds "
                    f"[{left_x:.2f}, {right_x:.2f}] vs ±{max_abs_x:.2f}"
                )
            if bottom_y < min_y or top_y > max_y:
                raise ValueError(
                    f"Mobject {mob!r} exceeds vertical 9:16 safe bounds "
                    f"[{bottom_y:.2f}, {top_y:.2f}] vs [{min_y:.2f}, {max_y:.2f}]"
                )

    def run_segment(self, segment, duration: float) -> None:
        self._segment_start = self.renderer.time
        segment(duration)

    def _pad(self, target_dur: float, spent: float | None = None) -> None:
        # `spent` is accepted for existing scenes, but actual renderer time is authoritative.
        VerticalShortScene.check_frame_bounds(self)
        elapsed = self.renderer.time - self._segment_start
        rem = target_dur - elapsed
        if rem < -1 / 30:
            raise ValueError(f"Scene animations exceed narration by {-rem:.3f}s")
        if rem > 0:
            self.wait(rem)
