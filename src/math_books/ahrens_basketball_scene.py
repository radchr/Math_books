"""Vertical (9:16) Manim animation: Basketball adaptation of Ahrens' 1924 Chapter I game."""

from __future__ import annotations

import numpy as np
from manim import (
    DOWN,
    GRAY_B,
    LEFT,
    RIGHT,
    UP,
    WHITE,
    Arrow,
    Circle,
    Create,
    FadeIn,
    FadeOut,
    GrowFromCenter,
    MathTex,
    RoundedRectangle,
    Text,
    VGroup,
    Write,
)

from math_books.video_ui import (
    ACCENT_CYAN,
    ACCENT_GOLD,
    ACCENT_MINT,
    ACCENT_ORANGE,
    FONT,
    VerticalShortScene,
    configure_vertical_9_16,
    make_badge,
    make_basketball,
    make_caption,
    make_scoreboard,
    make_subtitle,
)

configure_vertical_9_16()


class AhrensBasketball(VerticalShortScene):
    """Vertical 9:16 short adapting Ahrens' 1924 'Race to 100' into a basketball 21-point duel."""

    def construct(self) -> None:
        dur = self._load_durations("video_ahrens")

        self.run_segment(self.scene_01_hook, dur["01_hook"])
        self.run_segment(self.scene_02_rules, dur["02_rules"])
        self.run_segment(self.scene_03_key_17, dur["03_key_17"])
        self.run_segment(self.scene_04_chain, dur["04_chain"])
        self.run_segment(self.scene_05_challenge, dur["05_challenge"])

    def scene_01_hook(self, total_dur: float) -> None:
        badge = make_badge("КНИГА В. АРЕНСА • 1924", ACCENT_ORANGE)
        subtitle = make_subtitle("Секрет дуэли 1 на 1")

        book = RoundedRectangle(
            corner_radius=0.2,
            width=3.4,
            height=4.1,
            fill_color="#3D2B1F",
            fill_opacity=0.95,
            stroke_color=ACCENT_GOLD,
            stroke_width=4,
        ).move_to(UP * 1.1)
        book_lbl = VGroup(
            Text("МАТЕМАТИЧЕСКИЕ", font=FONT, font_size=24, weight="BOLD", color=ACCENT_GOLD),
            Text("ИГРЫ", font=FONT, font_size=30, weight="BOLD", color=ACCENT_GOLD),
            Text("1924", font=FONT, font_size=32, weight="BOLD", color=WHITE),
        ).arrange(DOWN, buff=0.28)
        if book_lbl.width > book.width - 0.5:
            book_lbl.scale_to_fit_width(book.width - 0.5)
        book_lbl.move_to(book.get_center())
        book_grp = VGroup(book, book_lbl)

        ball = make_basketball(1.1).move_to(UP * 1.1)
        win_txt = Text("100% ПОБЕДА", font=FONT, font_size=46, weight="BOLD", color=ACCENT_MINT).move_to(DOWN * 1.3)
        cap = make_caption("Математика, которая\nвыигрывает матчи!", y=-4.6)

        self.play(FadeIn(badge, shift=DOWN * 0.3), FadeIn(subtitle), GrowFromCenter(book_grp), run_time=1.4)
        self.play(book_grp.animate.scale(0.6).shift(LEFT * 2.1), FadeIn(ball.shift(RIGHT * 1.6)), run_time=1.3)
        self.play(Write(win_txt), FadeIn(cap, shift=UP * 0.2), run_time=1.4)
        self._pad(total_dur, 4.1)
        self.play(FadeOut(VGroup(badge, subtitle, book_grp, ball, win_txt, cap)), run_time=0.4)

    def scene_02_rules(self, total_dur: float) -> None:
        badge = make_badge("ПРАВИЛА ИГРЫ ДО 21", ACCENT_CYAN)
        subtitle = make_subtitle("Общее табло на двоих")

        sb = make_scoreboard("00", "ОБЩИЙ СЧЁТ", y=2.1)
        pills = VGroup()
        for idx, (lbl, col) in enumerate([("+1", ACCENT_MINT), ("+2", ACCENT_CYAN), ("+3", ACCENT_ORANGE)]):
            c = Circle(radius=0.68, fill_color=col, fill_opacity=0.95, stroke_color=WHITE, stroke_width=3)
            t = Text(lbl, font=FONT, font_size=38, weight="BOLD", color=WHITE).move_to(c.get_center())
            pills.add(VGroup(c, t).move_to(np.array([(idx - 1) * 2.1, -0.6, 0])))

        goal = Text("Цель: забить ровно 21!", font=FONT, font_size=36, weight="BOLD", color=ACCENT_GOLD).move_to(
            DOWN * 2.4
        )
        cap = make_caption("Ходите по очереди: +1, +2 или +3.\nКто сделает 21 — победил!", y=-4.6)

        self.play(FadeIn(badge), FadeIn(subtitle), FadeIn(sb), run_time=1.4)
        self.play(FadeIn(pills, lag_ratio=0.2), run_time=1.4)
        # Animate score jumps: 00 -> 02 -> 05 -> 21
        for new_val in ["02", "05", "21"]:
            new_num = Text(
                new_val, font=FONT, font_size=82, weight="BOLD", color=ACCENT_MINT if new_val == "21" else ACCENT_GOLD
            ).move_to(sb[2].get_center())
            self.play(FadeOut(sb[2], run_time=0.2), FadeIn(new_num, run_time=0.25))
            sb[2] = new_num
            self.wait(0.35)

        self.play(Write(goal), FadeIn(cap, shift=UP * 0.2), run_time=1.4)
        self._pad(total_dur, 6.6)
        self.play(FadeOut(VGroup(badge, subtitle, sb, pills, goal, cap)), run_time=0.4)

    def scene_03_key_17(self, total_dur: float) -> None:
        badge = make_badge("СЕКРЕТ • СЧИТАЕМ С КОНЦА", ACCENT_ORANGE)
        subtitle = make_subtitle("Ключевое число — 17!")

        # Number line 17..21
        nums = [17, 18, 19, 20, 21]
        nodes = VGroup()
        for i, n in enumerate(nums):
            x = (i - 2) * 1.55
            col = ACCENT_GOLD if n == 17 else (ACCENT_MINT if n == 21 else "#2B3A55")
            txt_col = "#0D1B2A" if n in (17, 21) else WHITE
            c = Circle(radius=0.52, fill_color=col, fill_opacity=1.0, stroke_color=WHITE, stroke_width=2.5).move_to(
                [x, 2.3, 0]
            )
            t = Text(str(n), font=FONT, font_size=34, weight="BOLD", color=txt_col).move_to(c.get_center())
            nodes.add(VGroup(c, t))

        b1 = Text(
            "Соперник +3 → 20   ⇒   Ты +1 → 21!", font=FONT, font_size=30, weight="BOLD", color=ACCENT_CYAN
        ).move_to(UP * 0.2)
        b2 = Text(
            "Соперник +1 → 18   ⇒   Ты +3 → 21!", font=FONT, font_size=30, weight="BOLD", color=ACCENT_MINT
        ).move_to(DOWN * 0.9)
        eq = MathTex(
            r"17 \xrightarrow{+1..+3} \{18, 19, 20\} \longrightarrow 21", color=ACCENT_GOLD, font_size=42
        ).move_to(DOWN * 2.2)
        cap = make_caption("Оставь сопернику 17 —\nи 21 уже у тебя в кармане!", y=-4.6)

        self.play(FadeIn(badge), FadeIn(subtitle), FadeIn(nodes, lag_ratio=0.15), run_time=1.6)
        self.play(Write(b1), run_time=1.8)
        self.play(Write(b2), run_time=1.8)
        self.play(Write(eq), FadeIn(cap, shift=UP * 0.2), run_time=1.6)
        self._pad(total_dur, 6.8)
        self.play(FadeOut(VGroup(badge, subtitle, nodes, b1, b2, eq, cap)), run_time=0.4)

    def scene_04_chain(self, total_dur: float) -> None:
        badge = make_badge("ВЫИГРЫШНАЯ ЦЕПОЧКА", ACCENT_MINT)
        subtitle = make_subtitle("Шаг = 1 + 3 = 4")

        chain_vals = [1, 5, 9, 13, 17, 21]
        pills = VGroup()
        arrows = VGroup()
        positions = [
            np.array([-2.2, 3.0, 0]),
            np.array([0.0, 3.0, 0]),
            np.array([2.2, 3.0, 0]),
            np.array([-2.2, 0.7, 0]),
            np.array([0.0, 0.7, 0]),
            np.array([2.2, 0.7, 0]),
        ]
        for val, pos in zip(chain_vals, positions, strict=True):
            col = ACCENT_ORANGE if val == 1 else (ACCENT_MINT if val == 21 else ACCENT_GOLD)
            c = Circle(radius=0.58, fill_color=col, fill_opacity=1.0, stroke_color=WHITE, stroke_width=3).move_to(pos)
            t = Text(str(val), font=FONT, font_size=36, weight="BOLD", color="#0D1B2A").move_to(pos)
            pills.add(VGroup(c, t))

        for i in range(len(positions) - 1):
            if i == 2:
                arr = Arrow(
                    positions[2] + DOWN * 0.65, positions[3] + UP * 0.65, buff=0.1, color=GRAY_B, stroke_width=4
                )
            else:
                arr = Arrow(
                    positions[i] + RIGHT * 0.62,
                    positions[i + 1] + LEFT * 0.62,
                    buff=0.05,
                    color=ACCENT_CYAN,
                    stroke_width=4,
                )
            arrows.add(arr)

        formula = Text("Шаг = 1 + 3 = 4", font=FONT, font_size=44, weight="BOLD", color=WHITE).move_to(DOWN * 1.4)
        tip = Text("Дополняй ход соперника до 4!", font=FONT, font_size=32, weight="BOLD", color=ACCENT_CYAN).move_to(
            DOWN * 2.5
        )
        cap = make_caption("Начни с 1 очка —\nи проиграть невозможно!", y=-4.6)

        self.play(FadeIn(badge), FadeIn(subtitle), run_time=1.2)
        self.play(FadeIn(pills, lag_ratio=0.18), Create(arrows, lag_ratio=0.18), run_time=2.6)
        self.play(Write(formula), FadeIn(tip), FadeIn(cap, shift=UP * 0.2), run_time=1.8)
        self._pad(total_dur, 5.6)
        self.play(FadeOut(VGroup(badge, subtitle, pills, arrows, formula, tip, cap)), run_time=0.4)

    def scene_05_challenge(self, total_dur: float) -> None:
        badge = make_badge("ЗАДАЧА ИЗ КНИГИ АРЕНСА", "#E63946")
        subtitle = make_subtitle("Табло до 100 • Ход от 1 до 10")

        sb = make_scoreboard("100", "КНИГА 1924 ГОДА", y=1.8)
        rng = Text("Можно добавлять: +1 ... +10", font=FONT, font_size=34, weight="BOLD", color=ACCENT_CYAN).move_to(
            DOWN * 0.4
        )
        q = Text("С какого числа начать?", font=FONT, font_size=40, weight="BOLD", color=WHITE).move_to(DOWN * 1.8)
        cap = make_caption("Посчитай шаг и первый ход!\nОтвет проверь с друзьями.", y=-4.6)

        self.play(FadeIn(badge), FadeIn(subtitle), FadeIn(sb), run_time=1.4)
        self.play(Write(rng), Write(q), FadeIn(cap, shift=UP * 0.2), run_time=1.8)
        self._pad(total_dur, 3.2)
        self.wait(0.3)
