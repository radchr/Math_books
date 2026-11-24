"""Vertical (9:16) Manim animation: MoneyBART in Basketball."""

from __future__ import annotations

import numpy as np
from manim import (
    DOWN,
    GRAY_B,
    RED_C,
    UP,
    WHITE,
    Arc,
    Circle,
    Create,
    FadeIn,
    FadeOut,
    MathTex,
    RoundedRectangle,
    Sector,
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


class MoneyBartBasketball(VerticalShortScene):
    """Vertical 9:16 short explaining expected value and Moneyball/MoneyBART in basketball."""

    def construct(self) -> None:
        dur = self._load_durations("video_moneybart")

        self.run_segment(self.scene_01_hook, dur["01_hook"])
        self.run_segment(self.scene_02_middle_trap, dur["02_middle_trap"])
        self.run_segment(self.scene_03_three_wins, dur["03_three_wins"])
        self.run_segment(self.scene_04_nba_map, dur["04_nba_map"])
        self.run_segment(self.scene_05_challenge, dur["05_challenge"])

    def scene_01_hook(self, total_dur: float) -> None:
        badge = make_badge("MONEYBART • ХАК ЛИЗЫ", ACCENT_ORANGE)
        subtitle = make_subtitle("Математика против интуиции")

        card = RoundedRectangle(
            corner_radius=0.25,
            width=6.8,
            height=2.6,
            fill_color=CARD_BG,
            fill_opacity=0.95,
            stroke_color=ACCENT_GOLD,
            stroke_width=3.5,
        ).move_to(UP * 1.8)
        c_title = Text("ЛИЗА СИМПСОН", font=FONT, font_size=36, weight="BOLD", color=ACCENT_GOLD).move_to(
            card.get_top() + DOWN * 0.55
        )
        c_sub = Text("Статистика  >  Догадки", font=FONT, font_size=32, weight="BOLD", color=ACCENT_MINT).move_to(
            card.get_center() + DOWN * 0.3
        )
        if c_sub.width > 6.2:
            c_sub.scale_to_fit_width(6.2)

        ball = make_basketball(0.8).move_to(DOWN * 1.1)
        cap = make_caption("Можно попадать реже,\nно набирать больше очков?", y=-4.5)

        self.play(FadeIn(badge, shift=DOWN * 0.3), FadeIn(subtitle), run_time=1.2)
        self.play(FadeIn(card), Write(c_title), Write(c_sub), FadeIn(ball), run_time=1.8)
        self.play(FadeIn(cap, shift=UP * 0.2), run_time=1.2)
        self._pad(total_dur, 4.2)
        self.play(FadeOut(VGroup(badge, subtitle, card, c_title, c_sub, ball, cap)), run_time=0.4)

    def scene_02_middle_trap(self, total_dur: float) -> None:
        badge = make_badge("ЛОВУШКА СРЕДНЕГО БРОСКА", "#E63946")
        subtitle = make_subtitle("50% попаданий — это круто?")

        court = make_half_court(center_y=1.1)
        top_y = court[0].get_top()[1]
        rim_pos = np.array([0.0, top_y - 0.55, 0])
        mid_zone = Sector(
            radius=2.6,
            start_angle=-np.pi,
            angle=np.pi,
            arc_center=rim_pos,
            fill_color=RED_C,
            fill_opacity=0.25,
            stroke_width=0,
        )

        eq = MathTex(r"50\% \times 2 = 1.00", color=ACCENT_GOLD, font_size=54).move_to(DOWN * 2.8)
        cap = make_caption("50% с 4 метров: в среднем\n1.00 очко за бросок.", y=-4.6)

        self.play(FadeIn(badge), FadeIn(subtitle), Create(court), run_time=1.2)
        self.play(FadeIn(mid_zone), Write(eq), FadeIn(cap, shift=UP * 0.2), run_time=1.8)
        self._pad(total_dur, 3.0)
        self.play(FadeOut(VGroup(badge, subtitle, court, mid_zone, eq, cap)), run_time=0.4)

    def scene_03_three_wins(self, total_dur: float) -> None:
        badge = make_badge("МАГИЯ ЛИЗЫ СИМПСОН", ACCENT_MINT)
        subtitle = make_subtitle("35% могут быть выгоднее 50%")

        eq3 = MathTex(r"35\% \times 3 = 1.05", color=ACCENT_MINT, font_size=56).move_to(UP * 2.6)
        cmp_txt = Text("1.05  >  1.00", font=FONT, font_size=48, weight="BOLD", color=ACCENT_GOLD).move_to(UP * 1.1)

        box = RoundedRectangle(
            corner_radius=0.25,
            width=7.6,
            height=2.5,
            fill_color="#09111E",
            fill_opacity=0.98,
            stroke_color=ACCENT_MINT,
            stroke_width=3,
        ).move_to(DOWN * 1.2)
        bhdr = Text("ОЖИДАНИЕ ЗА 100 БРОСКОВ:", font=FONT, font_size=26, weight="BOLD", color=GRAY_B).move_to(
            box.get_top() + DOWN * 0.45
        )
        bval = Text(
            "3-очковые: 105   vs   2-очковые: 100", font=FONT, font_size=32, weight="BOLD", color=WHITE
        ).move_to(box.get_center() + DOWN * 0.2)
        if bval.width > 7.0:
            bval.scale_to_fit_width(7.0)

        cap = make_caption("Больше очков в среднем.\nПобеда в матче не гарантирована!", y=-4.6)

        self.play(FadeIn(badge), FadeIn(subtitle), run_time=1.2)
        self.play(Write(eq3), Write(cmp_txt), run_time=1.8)
        self.play(FadeIn(box), FadeIn(bhdr), Write(bval), FadeIn(cap, shift=UP * 0.2), run_time=1.8)
        self._pad(total_dur, 4.8)
        self.play(FadeOut(VGroup(badge, subtitle, eq3, cmp_txt, box, bhdr, bval, cap)), run_time=0.4)

    def scene_04_nba_map(self, total_dur: float) -> None:
        badge = make_badge("РЕВОЛЮЦИЯ В NBA", ACCENT_CYAN)
        subtitle = make_subtitle("Выбор зависит от игрока и защиты")

        court = make_half_court(center_y=1.1)
        top_y = court[0].get_top()[1]
        rim_pos = np.array([0.0, top_y - 0.55, 0])

        dead_zone = Sector(
            radius=2.95,
            start_angle=-np.pi,
            angle=np.pi,
            arc_center=rim_pos,
            fill_color=RED_C,
            fill_opacity=0.28,
            stroke_width=0,
        )
        rim_zone = Circle(
            radius=0.9, fill_color=ACCENT_MINT, fill_opacity=0.55, stroke_color=ACCENT_MINT, stroke_width=3
        ).move_to(rim_pos)
        arc_zone = Arc(
            radius=3.3, start_angle=-np.pi + 0.15, angle=np.pi - 0.3, color=ACCENT_MINT, stroke_width=14
        ).move_arc_center_to(rim_pos)

        legend = Text("ПОД КОЛЬЦО  или  ИЗ-ЗА ДУГИ", font=FONT, font_size=32, weight="BOLD", color=ACCENT_MINT).move_to(
            DOWN * 2.8
        )
        if legend.width > 7.6:
            legend.scale_to_fit_width(7.6)
        cap = make_caption("Часто выгодно, но учитывай защиту.\nПодборы и штрафные здесь не считаем.", y=-4.6)

        self.play(FadeIn(badge), FadeIn(subtitle), Create(court), run_time=1.2)
        self.play(
            FadeIn(dead_zone),
            FadeIn(rim_zone),
            Create(arc_zone),
            Write(legend),
            FadeIn(cap, shift=UP * 0.2),
            run_time=2.0,
        )
        self._pad(total_dur, 3.2)
        self.play(FadeOut(VGroup(badge, subtitle, court, dead_zone, rim_zone, arc_zone, legend, cap)), run_time=0.4)

    def scene_05_challenge(self, total_dur: float) -> None:
        badge = make_badge("ЧЕЛЛЕНДЖ MONEYBART", ACCENT_ORANGE)
        subtitle = make_subtitle("Посчитай свою силу!")

        c1 = Text("10 средних бросков  →  Очки?", font=FONT, font_size=34, weight="BOLD", color=RED_C).move_to(UP * 1.8)
        c2 = Text("10 трёхочковых      →  Очки?", font=FONT, font_size=34, weight="BOLD", color=ACCENT_MINT).move_to(
            UP * 0.3
        )
        for t in (c1, c2):
            if t.width > 7.6:
                t.scale_to_fit_width(7.6)

        cap = make_caption("Сравнивай очки за бросок.\nПовтори опыт в другие дни!", y=-4.6)

        self.play(FadeIn(badge), FadeIn(subtitle), run_time=1.2)
        self.play(Write(c1), Write(c2), FadeIn(cap, shift=UP * 0.2), run_time=1.8)
        self._pad(total_dur, 3.0)
        self.wait(0.3)
