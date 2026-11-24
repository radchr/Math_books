"""Vertical (9:16) Manim animation: Triangles in Basketball, synced to Gemini TTS."""

from __future__ import annotations

import numpy as np
from manim import (
    BLUE_C,
    DOWN,
    GRAY_B,
    LEFT,
    RED_C,
    RIGHT,
    UP,
    WHITE,
    Circle,
    Create,
    DashedLine,
    Dot,
    FadeIn,
    FadeOut,
    GrowFromCenter,
    Line,
    MathTex,
    ParametricFunction,
    Polygon,
    Rectangle,
    Text,
    VGroup,
    Write,
)

from math_books.video_ui import (
    ACCENT_CYAN,
    ACCENT_GOLD,
    ACCENT_MINT,
    ACCENT_ORANGE,
    CARD_BG,
    FONT,
    VerticalShortScene,
    configure_vertical_9_16,
    make_badge,
    make_basketball,
    make_caption,
    make_half_court,
    make_subtitle,
)

configure_vertical_9_16()

__all__ = [
    "ACCENT_CYAN",
    "ACCENT_GOLD",
    "ACCENT_MINT",
    "ACCENT_ORANGE",
    "CARD_BG",
    "FONT",
    "BasketballTriangles",
    "make_badge",
    "make_basketball",
    "make_caption",
    "make_half_court",
    "make_subtitle",
]


class BasketballTriangles(VerticalShortScene):
    """Full 9:16 vertical short explaining 3 geometric secrets + 1 challenge in basketball."""

    def construct(self) -> None:
        dur = self._load_durations("video_basketball")

        self.run_segment(self.scene_01_hook, dur["01_hook"])
        self.run_segment(self.scene_02_triangle_offense, dur["02_triangle_offense"])
        self.run_segment(self.scene_03_bank_shot, dur["03_bank_shot"])
        self.run_segment(self.scene_04_arc_angle, dur["04_arc_angle"])
        self.run_segment(self.scene_05_challenge, dur["05_challenge"])

    def scene_01_hook(self, total_dur: float) -> None:
        t0 = 0.0

        badge = make_badge("ГЕОМЕТРИЯ БАСКЕТБОЛА", ACCENT_ORANGE)
        title = Text("ТРЕУГОЛЬНИКИ\nРЕШАЮТ ИГРУ", font=FONT, font_size=52, weight="BOLD", color=WHITE, line_spacing=1.2)
        title.move_to(UP * 4.2)

        # Stylized glowing triangle + hoop + ball
        p1 = np.array([-2.5, -1.6, 0])
        p2 = np.array([2.5, -1.6, 0])
        p3 = np.array([0.0, 2.1, 0])
        tri = Polygon(p1, p2, p3, stroke_color=ACCENT_GOLD, stroke_width=6, fill_color=ACCENT_ORANGE, fill_opacity=0.14)
        rim = Circle(radius=0.45, color=ACCENT_ORANGE, stroke_width=7).move_to(p3)
        ball = make_basketball(0.42).move_to(p1)
        cap = make_caption("Скучный учебник? Нет —\nэто секрет точного броска!", y=-4.8)

        self.play(FadeIn(badge, shift=DOWN * 0.3), Write(title), run_time=1.2)
        self.play(Create(tri), GrowFromCenter(rim), FadeIn(ball), run_time=1.5)
        self.play(ball.animate.move_to(p2), run_time=1.0)
        self.play(ball.animate.move_to(p3), FadeIn(cap, shift=UP * 0.3), run_time=1.2)
        t0 += 4.9
        self._pad(total_dur, t0)
        self.play(FadeOut(VGroup(badge, title, tri, rim, ball, cap)), run_time=0.4)

    def scene_02_triangle_offense(self, total_dur: float) -> None:
        badge = make_badge("СЕКРЕТ #1 • АТАКА", ACCENT_ORANGE)
        subtitle = Text("Нападение треугольником", font=FONT, font_size=38, weight="BOLD", color=ACCENT_GOLD).move_to(
            UP * 5.2
        )

        court = make_half_court(center_y=1.0)
        p1 = np.array([-2.2, 2.3, 0])
        p2 = np.array([-0.2, -0.4, 0])
        p3 = np.array([2.3, 1.5, 0])

        tri = Polygon(p1, p2, p3, stroke_color=ACCENT_GOLD, stroke_width=5, fill_color=ACCENT_ORANGE, fill_opacity=0.12)
        players = VGroup(
            VGroup(
                Dot(p1, radius=0.26, color=ACCENT_ORANGE), Text("1", font=FONT, font_size=24, weight="BOLD").move_to(p1)
            ),
            VGroup(
                Dot(p2, radius=0.26, color=ACCENT_ORANGE), Text("2", font=FONT, font_size=24, weight="BOLD").move_to(p2)
            ),
            VGroup(
                Dot(p3, radius=0.26, color=ACCENT_ORANGE), Text("3", font=FONT, font_size=24, weight="BOLD").move_to(p3)
            ),
        )
        d1 = Dot(np.array([-1.3, 1.2, 0]), radius=0.22, color=ACCENT_CYAN)
        d2 = Dot(np.array([0.8, 0.8, 0]), radius=0.22, color=ACCENT_CYAN)
        ball = make_basketball(0.24).move_to(p1)
        cap = make_caption("11 чемпионств NBA\n2 защитника не закроют 3 линии!", y=-4.5)

        self.play(FadeIn(badge), FadeIn(subtitle), Create(court), run_time=1.3)
        self.play(Create(tri), FadeIn(players), FadeIn(d1), FadeIn(d2), FadeIn(ball), run_time=1.5)
        # Pass 1 -> 2, defenders shift
        self.play(
            ball.animate.move_to(p2),
            d1.animate.move_to([-0.5, 0.4, 0]),
            d2.animate.move_to([0.3, 0.2, 0]),
            run_time=1.8,
        )
        # Pass 2 -> 3, player 3 open!
        self.play(
            ball.animate.move_to(p3), d2.animate.move_to([1.5, 1.0, 0]), FadeIn(cap, shift=UP * 0.2), run_time=1.8
        )
        # Open shot line to rim
        rim_pos = court[-1].get_center()
        shot_line = DashedLine(p3, rim_pos, color=ACCENT_MINT, stroke_width=5)
        self.play(Create(shot_line), ball.animate.move_to(rim_pos), run_time=1.4)
        self._pad(total_dur, 7.8)
        self.play(FadeOut(VGroup(badge, subtitle, court, tri, players, d1, d2, ball, shot_line, cap)), run_time=0.4)

    def scene_03_bank_shot(self, total_dur: float) -> None:
        badge = make_badge("СЕКРЕТ #2 • ОТ ЩИТА", ACCENT_CYAN)
        subtitle = Text("Равные треугольники", font=FONT, font_size=38, weight="BOLD", color=ACCENT_GOLD).move_to(
            UP * 5.2
        )

        # Top-down view of backboard + normal + congruent triangles
        board_y = 3.2
        backboard = Line(LEFT * 3.0, RIGHT * 3.0, color=WHITE, stroke_width=8).move_to(UP * board_y)
        target_sq = Rectangle(width=1.1, height=0.2, color=ACCENT_ORANGE, stroke_width=4).move_to(UP * (board_y - 0.1))
        rim = Circle(radius=0.45, color=ACCENT_ORANGE, stroke_width=6).move_to(UP * (board_y - 0.75))

        hit_pt = np.array([0.0, board_y, 0])
        shooter_pt = np.array([-2.8, -1.2, 0])
        # Symmetric reflection point for congruent triangle demo
        sym_pt = np.array([2.8, -1.2, 0])
        normal = DashedLine(hit_pt, np.array([0.0, -1.2, 0]), color=GRAY_B, stroke_width=3)

        tri1 = Polygon(
            shooter_pt,
            hit_pt,
            np.array([0.0, -1.2, 0]),
            stroke_color=ACCENT_CYAN,
            stroke_width=4,
            fill_color=ACCENT_CYAN,
            fill_opacity=0.18,
        )
        tri2 = Polygon(
            sym_pt,
            hit_pt,
            np.array([0.0, -1.2, 0]),
            stroke_color=ACCENT_MINT,
            stroke_width=4,
            fill_color=ACCENT_MINT,
            fill_opacity=0.18,
        )

        l_in = Line(shooter_pt, hit_pt, color=ACCENT_GOLD, stroke_width=5)
        l_out = Line(hit_pt, rim.get_center(), color=ACCENT_MINT, stroke_width=5)
        alpha_lbl = MathTex(r"\alpha", color=ACCENT_CYAN, font_size=44).move_to([-0.55, 1.8, 0])
        beta_lbl = MathTex(r"\beta", color=ACCENT_MINT, font_size=44).move_to([0.55, 1.8, 0])
        eq_lbl = MathTex(r"\alpha = \beta", color=WHITE, font_size=48).move_to(DOWN * 2.2)

        ball = make_basketball(0.32).move_to(shooter_pt)
        cap = make_caption("Угол падения = углу отскока\nЦелься в угол квадрата!", y=-4.5)

        self.play(FadeIn(badge), FadeIn(subtitle), Create(backboard), Create(target_sq), Create(rim), run_time=1.3)
        self.play(Create(normal), Create(tri1), Create(tri2), FadeIn(alpha_lbl), FadeIn(beta_lbl), run_time=1.8)
        self.play(Create(l_in), FadeIn(ball), Write(eq_lbl), run_time=1.4)
        self.play(ball.animate.move_to(hit_pt), run_time=1.2)
        self.play(Create(l_out), ball.animate.move_to(rim.get_center()), FadeIn(cap, shift=UP * 0.2), run_time=1.4)
        self._pad(total_dur, 7.1)
        self.play(
            FadeOut(
                VGroup(
                    badge,
                    subtitle,
                    backboard,
                    target_sq,
                    rim,
                    normal,
                    tri1,
                    tri2,
                    l_in,
                    l_out,
                    alpha_lbl,
                    beta_lbl,
                    eq_lbl,
                    ball,
                    cap,
                )
            ),
            run_time=0.4,
        )

    def scene_04_arc_angle(self, total_dur: float) -> None:
        badge = make_badge("СЕКРЕТ #3 • ВЫСОКАЯ ДУГА", ACCENT_ORANGE)
        subtitle = Text("Угол решает размер кольца", font=FONT, font_size=36, weight="BOLD", color=ACCENT_GOLD).move_to(
            UP * 5.2
        )

        # Side view: shooter at (-2.8, -0.8), hoop at (2.8, 1.2)
        start = np.array([-2.7, -0.5, 0])
        end = np.array([2.7, 1.3, 0])
        corner = np.array([2.7, -0.5, 0])

        tri = Polygon(start, corner, end, stroke_color=GRAY_B, stroke_width=3, fill_color=BLUE_C, fill_opacity=0.08)
        rim = Line(np.array([2.35, 1.3, 0]), np.array([3.05, 1.3, 0]), color=ACCENT_ORANGE, stroke_width=8)
        backboard = Line(np.array([3.1, 1.1, 0]), np.array([3.1, 2.4, 0]), color=WHITE, stroke_width=6)

        flat_arc = ParametricFunction(
            lambda t: np.array(
                [
                    start[0] + (end[0] - start[0]) * t,
                    start[1] + (end[1] - start[1]) * t + 1.1 * 4 * t * (1 - t),
                    0,
                ]
            ),
            t_range=[0, 1],
            color=RED_C,
            stroke_width=4,
        )
        high_arc = ParametricFunction(
            lambda t: np.array(
                [
                    start[0] + (end[0] - start[0]) * t,
                    start[1] + (end[1] - start[1]) * t + 3.0 * 4 * t * (1 - t),
                    0,
                ]
            ),
            t_range=[0, 1],
            color=ACCENT_MINT,
            stroke_width=6,
        )

        ang_lbl = MathTex(r"48^\circ", color=ACCENT_GOLD, font_size=46).move_to([-1.2, 0.2, 0])
        flat_txt = Text("30° — узкая щель", font=FONT, font_size=28, color=RED_C).move_to([-1.4, -2.1, 0])
        high_txt = Text("48° — широкое кольцо!", font=FONT, font_size=30, weight="BOLD", color=ACCENT_MINT).move_to(
            [1.2, -2.8, 0]
        )

        ball = make_basketball(0.28).move_to(start)
        cap = make_caption("Чем выше дуга (~48°),\nтем шире цель для мяча!", y=-4.6)

        self.play(FadeIn(badge), FadeIn(subtitle), Create(tri), Create(rim), Create(backboard), run_time=1.3)
        self.play(Create(flat_arc), FadeIn(flat_txt), run_time=1.3)
        self.play(Create(high_arc), Write(ang_lbl), FadeIn(high_txt), FadeIn(ball), run_time=1.6)
        self.play(ball.animate.move_to(end), FadeIn(cap, shift=UP * 0.2), run_time=1.8)
        self._pad(total_dur, 6.0)
        self.play(
            FadeOut(
                VGroup(badge, subtitle, tri, rim, backboard, flat_arc, high_arc, ang_lbl, flat_txt, high_txt, ball, cap)
            ),
            run_time=0.4,
        )

    def scene_05_challenge(self, total_dur: float) -> None:
        badge = make_badge("ЧЕЛЛЕНДЖ ДЛЯ ТЕБЯ!", "#E63946")
        subtitle = make_subtitle("Где угол обзора кольца больше?")

        court = make_half_court(center_y=1.0)
        top_y = court[0].get_top()[1]
        rim_l = np.array([-0.24, top_y - 0.55, 0])
        rim_r = np.array([0.24, top_y - 0.55, 0])

        center_pt = np.array([0.0, top_y - 3.65, 0])
        corner_pt = np.array([3.1, top_y - 0.55, 0])

        tri_c = Polygon(
            center_pt, rim_l, rim_r, stroke_color=ACCENT_CYAN, stroke_width=4, fill_color=ACCENT_CYAN, fill_opacity=0.22
        )
        tri_u = Polygon(
            corner_pt,
            rim_l,
            rim_r,
            stroke_color=ACCENT_ORANGE,
            stroke_width=4,
            fill_color=ACCENT_ORANGE,
            fill_opacity=0.22,
        )

        dot_c = Dot(center_pt, radius=0.22, color=ACCENT_CYAN)
        dot_u = Dot(corner_pt, radius=0.22, color=ACCENT_ORANGE)
        lbl_c = Text("ЦЕНТР", font=FONT, font_size=26, weight="BOLD", color=ACCENT_CYAN).next_to(dot_c, DOWN, buff=0.2)
        lbl_u = Text("УГОЛ", font=FONT, font_size=26, weight="BOLD", color=ACCENT_ORANGE).next_to(dot_u, DOWN, buff=0.2)

        q_txt = Text("ЦЕНТР  или  УГОЛ ?", font=FONT, font_size=40, weight="BOLD", color=WHITE).move_to(DOWN * 3.0)
        cap = make_caption("Подумай и проверь\nсегодня на тренировке!", y=-4.8)

        self.play(FadeIn(badge), FadeIn(subtitle), Create(court), run_time=1.3)
        self.play(Create(tri_c), FadeIn(dot_c), FadeIn(lbl_c), run_time=1.6)
        self.play(Create(tri_u), FadeIn(dot_u), FadeIn(lbl_u), run_time=1.6)
        self.play(Write(q_txt), FadeIn(cap, shift=UP * 0.2), run_time=1.5)
        self._pad(total_dur, 6.0)
        self.wait(0.3)
