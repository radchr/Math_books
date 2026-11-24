"""Vertical (9:16) Manim animation: The Hot Hand Paradox in Basketball (Miller & Sanjurjo)."""

from __future__ import annotations

import numpy as np
from manim import (
    DOWN,
    GRAY_B,
    LEFT,
    RED_C,
    RIGHT,
    UP,
    WHITE,
    Circle,
    Create,
    FadeIn,
    FadeOut,
    GrowFromCenter,
    Line,
    MathTex,
    RoundedRectangle,
    Text,
    VGroup,
    Write,
)

from math_books.lesson_math import coin_followup_examples
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
    make_subtitle,
)

configure_vertical_9_16()


def make_coin(label: str, color: str, radius: float = 0.48) -> VGroup:
    """Create a stylized coin token."""
    c = Circle(
        radius=radius,
        fill_color=color,
        fill_opacity=0.95,
        stroke_color=WHITE,
        stroke_width=3,
    )
    t = Text(label, font=FONT, font_size=34, weight="BOLD", color="#0D1B2A").move_to(c.get_center())
    return VGroup(c, t)


class HotHandBasketball(VerticalShortScene):
    """Vertical 9:16 short explaining the counterintuitive Hot Hand probability paradox."""

    def construct(self) -> None:
        dur = self._load_durations("video_hothand")

        self.run_segment(self.scene_01_hook, dur["01_hook"])
        self.run_segment(self.scene_02_coin_trap, dur["02_coin_trap"])
        self.run_segment(self.scene_03_paradox, dur["03_paradox"])
        self.run_segment(self.scene_04_nba_revenge, dur["04_nba_revenge"])
        self.run_segment(self.scene_05_challenge, dur["05_challenge"])

    def scene_01_hook(self, total_dur: float) -> None:
        badge = make_badge("ЭФФЕКТ ГОРЯЧЕЙ РУКИ", ACCENT_ORANGE)
        subtitle = make_subtitle("Миф или реальность?")

        # Glowing "on fire" basketball with concentric energy rings
        ring_outer = Circle(radius=1.55, color=ACCENT_ORANGE, stroke_width=4, stroke_opacity=0.45).move_to(UP * 1.4)
        ring_inner = Circle(radius=1.22, color=ACCENT_GOLD, stroke_width=5, stroke_opacity=0.75).move_to(UP * 1.4)
        ball = make_basketball(0.92).move_to(UP * 1.4)

        myth_card = RoundedRectangle(
            corner_radius=0.25,
            width=7.2,
            height=1.7,
            fill_color=CARD_BG,
            fill_opacity=0.95,
            stroke_color=RED_C,
            stroke_width=3,
        ).move_to(DOWN * 1.3)
        myth_txt = Text("Два попадания — уже закономерность?", font=FONT, font_size=32, weight="BOLD", color=RED_C)
        if myth_txt.width > 6.6:
            myth_txt.scale_to_fit_width(6.6)
        myth_txt.move_to(myth_card.get_top() + DOWN * 0.5)
        truth_txt = Text("Способ подсчёта может обмануть!", font=FONT, font_size=30, weight="BOLD", color=ACCENT_MINT)
        if truth_txt.width > 6.6:
            truth_txt.scale_to_fit_width(6.6)
        truth_txt.move_to(myth_card.get_bottom() + UP * 0.5)

        cap = make_caption("Как считать серии попаданий?\nНачнём с честной монетки.", y=-4.6)

        self.play(FadeIn(badge, shift=DOWN * 0.3), FadeIn(subtitle), run_time=1.2)
        self.play(GrowFromCenter(ball), Create(ring_inner), Create(ring_outer), run_time=1.5)
        self.play(FadeIn(myth_card), Write(myth_txt), run_time=1.4)
        self.play(Write(truth_txt), FadeIn(cap, shift=UP * 0.2), run_time=1.4)
        self._pad(total_dur, 5.5)
        self.play(
            FadeOut(VGroup(badge, subtitle, ring_outer, ring_inner, ball, myth_card, myth_txt, truth_txt, cap)),
            run_time=0.4,
        )

    def scene_02_coin_trap(self, total_dur: float) -> None:
        badge = make_badge("ЛОВУШКА МОНЕТКИ", ACCENT_CYAN)
        subtitle = make_subtitle("3 броска • 50 на 50")

        c1 = make_coin("О", ACCENT_GOLD, radius=0.62).move_to([-2.1, 2.2, 0])
        c2 = make_coin("?", ACCENT_CYAN, radius=0.62).move_to([0.0, 2.2, 0])
        c3 = make_coin("?", GRAY_B, radius=0.62).move_to([2.1, 2.2, 0])
        lbl1 = Text("Орёл", font=FONT, font_size=26, color=ACCENT_GOLD).next_to(c1, DOWN, buff=0.25)
        lbl2 = Text("После орла?", font=FONT, font_size=26, color=ACCENT_CYAN).next_to(c2, DOWN, buff=0.25)

        q_box = RoundedRectangle(
            corner_radius=0.25,
            width=7.2,
            height=2.1,
            fill_color=CARD_BG,
            fill_opacity=0.95,
            stroke_color=ACCENT_GOLD,
            stroke_width=3,
        ).move_to(DOWN * 1.1)
        q_hdr = Text("Шанс снова выбить ОРЛА?", font=FONT, font_size=30, weight="BOLD", color=WHITE).move_to(
            q_box.get_top() + DOWN * 0.55
        )
        q_ans = Text("Следующий бросок: 50%", font=FONT, font_size=38, weight="BOLD", color=ACCENT_GOLD).move_to(
            q_box.get_bottom() + UP * 0.65
        )
        if q_ans.width > 6.6:
            q_ans.scale_to_fit_width(6.6)

        cap = make_caption("А среднее долей по коротким сериям\nможет оказаться другим!", y=-4.6)

        self.play(FadeIn(badge), FadeIn(subtitle), run_time=1.2)
        self.play(FadeIn(c1), FadeIn(c2), FadeIn(c3), FadeIn(lbl1), FadeIn(lbl2), run_time=1.6)
        self.play(FadeIn(q_box), Write(q_hdr), run_time=1.4)
        self.play(Write(q_ans), FadeIn(cap, shift=UP * 0.2), run_time=1.4)
        self._pad(total_dur, 5.6)
        self.play(FadeOut(VGroup(badge, subtitle, c1, c2, c3, lbl1, lbl2, q_box, q_hdr, q_ans, cap)), run_time=0.4)

    def scene_03_paradox(self, total_dur: float) -> None:
        badge = make_badge("ЛОВУШКА УСРЕДНЕНИЯ", "#E63946")
        subtitle = make_subtitle("6 серий с броском после орла")

        rows_data = [
            ("  ".join(seq), f"{float(rate) * 100:.0f}%", ACCENT_MINT if rate == 1 else ACCENT_GOLD if rate else RED_C)
            for seq, rate in coin_followup_examples()
        ]
        table_grp = VGroup()
        for idx, (seq, pct, col) in enumerate(rows_data):
            col_i = idx // 3
            row_i = idx % 3
            x = -1.95 if col_i == 0 else 1.95
            y = 3.2 - row_i * 1.15
            card = RoundedRectangle(
                corner_radius=0.18,
                width=3.55,
                height=0.92,
                fill_color=CARD_BG,
                fill_opacity=0.95,
                stroke_color=col,
                stroke_width=2.5,
            ).move_to([x, y, 0])
            s_txt = Text(seq, font=FONT, font_size=28, weight="BOLD", color=WHITE).move_to(
                card.get_left() + RIGHT * 1.05
            )
            p_txt = Text(pct, font=FONT, font_size=28, weight="BOLD", color=col).move_to(card.get_right() + LEFT * 0.72)
            table_grp.add(VGroup(card, s_txt, p_txt))

        formula = MathTex(
            r"\frac{1 + 1/2 + 0 + 0 + 1 + 0}{6} = \frac{5}{12} \approx 42\%", color=ACCENT_GOLD, font_size=44
        )
        if formula.width > 7.6:
            formula.scale_to_fit_width(7.6)
        formula.move_to(DOWN * 1.35)

        shock = Text("ООР → после О: О, Р → 1/2", font=FONT, font_size=30, weight="BOLD", color=ACCENT_CYAN).move_to(
            DOWN * 2.55
        )
        if shock.width > 7.6:
            shock.scale_to_fit_width(7.6)
        cap = make_caption("42% — среднее шести долей.\nШанс следующего орла всё ещё 50%.", y=-4.6)

        self.play(FadeIn(badge), FadeIn(subtitle), run_time=1.2)
        self.play(FadeIn(table_grp, lag_ratio=0.15), run_time=2.2)
        self.play(Write(formula), run_time=1.8)
        self.play(Write(shock), FadeIn(cap, shift=UP * 0.2), run_time=1.4)
        self._pad(total_dur, 6.6)
        self.play(FadeOut(VGroup(badge, subtitle, table_grp, formula, shock, cap)), run_time=0.4)

    def scene_04_nba_revenge(self, total_dur: float) -> None:
        badge = make_badge("ОДНИ ДАННЫЕ — РАЗНЫЕ ВЕСА", ACCENT_MINT)
        subtitle = make_subtitle("Среднее долей ≠ общая доля")

        # Two estimators on the same coin data; neither is a basketball bonus.
        base_y = -1.6
        axis = Line(LEFT * 3.2, RIGHT * 3.2, color=GRAY_B, stroke_width=3).move_to([0, base_y, 0])

        bar_rand = RoundedRectangle(
            corner_radius=0.15,
            width=2.1,
            height=3.2,
            fill_color=RED_C,
            fill_opacity=0.88,
            stroke_color=WHITE,
            stroke_width=2.5,
        ).move_to([-1.6, base_y + 1.6, 0])
        lbl_rand_val = Text("42%", font=FONT, font_size=40, weight="BOLD", color=WHITE).move_to(bar_rand.get_center())
        lbl_rand_bot = Text("По сериям", font=FONT, font_size=26, weight="BOLD", color=RED_C).next_to(
            bar_rand, DOWN, buff=0.3
        )

        bar_real = RoundedRectangle(
            corner_radius=0.15,
            width=2.1,
            height=3.84,
            fill_color=ACCENT_MINT,
            fill_opacity=0.92,
            stroke_color=WHITE,
            stroke_width=2.5,
        ).move_to([1.6, base_y + 1.92, 0])
        lbl_real_val = Text("50%", font=FONT, font_size=40, weight="BOLD", color="#0D1B2A").move_to(
            bar_real.get_center()
        )
        lbl_real_bot = Text("Все переходы", font=FONT, font_size=26, weight="BOLD", color=ACCENT_MINT).next_to(
            bar_real, DOWN, buff=0.3
        )

        boost = Text(
            "После О: О О | О Р | Р | Р | О | Р\n4 орла из 8 переходов = 50%",
            font=FONT,
            font_size=24,
            weight="BOLD",
            color=ACCENT_GOLD,
        ).move_to([0, 3.65, 0])
        if boost.width > 7.6:
            boost.scale_to_fit_width(7.6)
        cap = make_caption("Этот пример не вычисляет бонус\nк точности баскетболиста.", y=-4.6)

        self.play(FadeIn(badge), FadeIn(subtitle), Create(axis), run_time=1.2)
        self.play(FadeIn(bar_rand, shift=UP * 0.4), FadeIn(lbl_rand_val), FadeIn(lbl_rand_bot), run_time=1.5)
        self.play(FadeIn(bar_real, shift=UP * 0.4), FadeIn(lbl_real_val), FadeIn(lbl_real_bot), run_time=1.5)
        self.play(Write(boost), FadeIn(cap, shift=UP * 0.2), run_time=1.4)
        self._pad(total_dur, 5.6)
        self.play(
            FadeOut(
                VGroup(
                    badge,
                    subtitle,
                    axis,
                    bar_rand,
                    lbl_rand_val,
                    lbl_rand_bot,
                    bar_real,
                    lbl_real_val,
                    lbl_real_bot,
                    boost,
                    cap,
                )
            ),
            run_time=0.4,
        )

    def scene_05_challenge(self, total_dur: float) -> None:
        badge = make_badge("ЧЕЛЛЕНДЖ ДЛЯ ТЕБЯ!", ACCENT_ORANGE)
        subtitle = make_subtitle("Проверь парадокс сам!")

        coins = VGroup(
            make_coin("О", ACCENT_GOLD, radius=0.58).move_to(np.array([-1.9, 2.3, 0])),
            make_coin("О", ACCENT_MINT, radius=0.58).move_to(np.array([0.0, 2.3, 0])),
            make_coin("Р", ACCENT_CYAN, radius=0.58).move_to(np.array([1.9, 2.3, 0])),
        )
        steps_card = RoundedRectangle(
            corner_radius=0.25,
            width=7.4,
            height=2.6,
            fill_color=CARD_BG,
            fill_opacity=0.95,
            stroke_color=ACCENT_GOLD,
            stroke_width=3,
        ).move_to(DOWN * 0.4)
        steps_txt = Text(
            "1. Выпиши 8 серий\n2. Исключи 2 без переходов\n3. Сравни два средних!",
            font=FONT,
            font_size=32,
            weight="BOLD",
            color=WHITE,
            line_spacing=1.35,
        ).move_to(steps_card.get_center())
        if steps_txt.width > 6.8:
            steps_txt.scale_to_fit_width(6.8)

        ball = make_basketball(0.45).move_to(DOWN * 2.55)
        cap = make_caption("Два попадания подряд —\nещё не доказательство эффекта.", y=-4.6)

        self.play(FadeIn(badge), FadeIn(subtitle), FadeIn(coins, lag_ratio=0.2), run_time=1.5)
        self.play(FadeIn(steps_card), Write(steps_txt), run_time=1.8)
        self.play(GrowFromCenter(ball), FadeIn(cap, shift=UP * 0.2), run_time=1.3)
        self._pad(total_dur, 4.6)
        self.wait(0.3)
