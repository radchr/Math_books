"""Vertical (9:16) Manim animation: Simpson's Paradox in Basketball."""

from __future__ import annotations

from manim import (
    DOWN,
    GRAY_B,
    RED_C,
    UP,
    WHITE,
    FadeIn,
    FadeOut,
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
    CARD_BG,
    FONT,
    VerticalShortScene,
    configure_vertical_9_16,
    make_badge,
    make_caption,
    make_stat_card,
    make_subtitle,
)

configure_vertical_9_16()


class SimpsonBasketball(VerticalShortScene):
    """Vertical 9:16 short explaining Simpson's Paradox through basketball shooting stats."""

    def construct(self) -> None:
        dur = self._load_durations("video_simpson")

        self.run_segment(self.scene_01_hook, dur["01_hook"])
        self.run_segment(self.scene_02_duel_stats, dur["02_duel_stats"])
        self.run_segment(self.scene_03_paradox, dur["03_paradox"])
        self.run_segment(self.scene_04_secret, dur["04_secret"])
        self.run_segment(self.scene_05_challenge, dur["05_challenge"])

    def scene_01_hook(self, total_dur: float) -> None:
        badge = make_badge("ПАРАДОКС СИМПСОНА", ACCENT_ORANGE)
        subtitle = make_subtitle("Не Гомер, а математик!")

        c1 = RoundedRectangle(
            corner_radius=0.25,
            width=3.5,
            height=3.1,
            fill_color=CARD_BG,
            fill_opacity=0.95,
            stroke_color=RED_C,
            stroke_width=3,
        ).move_to([-2.0, 1.2, 0])
        t1 = (
            VGroup(
                Text("ГОМЕР", font=FONT, font_size=34, weight="BOLD", color=ACCENT_GOLD),
                Text("СИМПСОН?", font=FONT, font_size=30, weight="BOLD", color=ACCENT_GOLD),
                Text("НЕТ!", font=FONT, font_size=40, weight="BOLD", color=RED_C),
            )
            .arrange(DOWN, buff=0.25)
            .move_to(c1.get_center())
        )

        c2 = RoundedRectangle(
            corner_radius=0.25,
            width=3.8,
            height=3.1,
            fill_color=CARD_BG,
            fill_opacity=0.95,
            stroke_color=ACCENT_MINT,
            stroke_width=3,
        ).move_to([2.0, 1.2, 0])
        t2 = (
            VGroup(
                Text("ЭДВАРД", font=FONT, font_size=30, weight="BOLD", color=ACCENT_MINT),
                Text("СИМПСОН", font=FONT, font_size=30, weight="BOLD", color=ACCENT_MINT),
                Text("1951 • Взломщик\nшифров", font=FONT, font_size=22, color=WHITE, line_spacing=1.2),
            )
            .arrange(DOWN, buff=0.22)
            .move_to(c2.get_center())
        )

        cap = make_caption("Точнее в обоих бросках,\nно хуже в сумме — как так?", y=-4.5)

        self.play(FadeIn(badge, shift=DOWN * 0.3), FadeIn(subtitle), run_time=1.3)
        self.play(FadeIn(c1), FadeIn(t1), run_time=1.6)
        self.play(FadeIn(c2), FadeIn(t2), run_time=1.8)
        self.play(FadeIn(cap, shift=UP * 0.2), run_time=1.2)
        self._pad(total_dur, 5.9)
        self.play(FadeOut(VGroup(badge, subtitle, c1, t1, c2, t2, cap)), run_time=0.4)

    def scene_02_duel_stats(self, total_dur: float) -> None:
        badge = make_badge("ДУЭЛЬ: АЛЕКС vs МАКС", ACCENT_CYAN)
        subtitle = make_subtitle("По 100 бросков у каждого")

        card2p = make_stat_card(
            "2-ОЧКОВЫЕ БРОСКИ", "Алекс: 60%\n(6 из 10)", "Макс: 50%\n(45 из 90)", y=2.5, highlight_left=True
        )
        card3p = make_stat_card(
            "3-ОЧКОВЫЕ БРОСКИ", "Алекс: 40%\n(36 из 90)", "Макс: 30%\n(3 из 10)", y=-0.3, highlight_left=True
        )
        cap = make_caption("Алекс точнее и с двухочковой,\nи с трёхочковой дистанции!", y=-4.5)

        self.play(FadeIn(badge), FadeIn(subtitle), run_time=1.2)
        self.play(FadeIn(card2p, shift=UP * 0.3), run_time=1.8)
        self.play(FadeIn(card3p, shift=UP * 0.3), run_time=1.8)
        self.play(FadeIn(cap, shift=UP * 0.2), run_time=1.2)
        self._pad(total_dur, 6.0)
        self.play(FadeOut(VGroup(badge, subtitle, card2p, card3p, cap)), run_time=0.4)

    def scene_03_paradox(self, total_dur: float) -> None:
        badge = make_badge("ВЗРЫВ МОЗГА!", "#E63946")
        subtitle = make_subtitle("Считаем общий процент")

        card_tot = make_stat_card(
            "ВСЕГО ПОПАДАНИЙ ИЗ 100",
            "Алекс: 42%\n(6 + 36 = 42)",
            "Макс: 48%\n(45 + 3 = 48)",
            y=1.8,
            highlight_left=False,
        )
        ineq = Text("42%  <  48%  ?!", font=FONT, font_size=52, weight="BOLD", color=ACCENT_GOLD).move_to(DOWN * 1.1)
        cap = make_caption("Алекс выиграл обе категории,\nно проиграл в общей таблице!", y=-4.5)

        self.play(FadeIn(badge), FadeIn(subtitle), run_time=1.2)
        self.play(FadeIn(card_tot, shift=UP * 0.3), run_time=1.8)
        self.play(Write(ineq), FadeIn(cap, shift=UP * 0.2), run_time=1.6)
        self._pad(total_dur, 4.6)
        self.play(FadeOut(VGroup(badge, subtitle, card_tot, ineq, cap)), run_time=0.4)

    def scene_04_secret(self, total_dur: float) -> None:
        badge = make_badge("РАЗГАДКА ПАРАДОКСА", ACCENT_MINT)
        subtitle = make_subtitle("Всё решают объёмы бросков")

        a_txt = Text(
            "Алекс:  90 трёхочковых  +  10 двухочковых", font=FONT, font_size=28, weight="BOLD", color=ACCENT_CYAN
        ).move_to(UP * 2.8)
        m_txt = Text(
            "Макс:   90 двухочковых  +  10 трёхочковых", font=FONT, font_size=28, weight="BOLD", color=ACCENT_ORANGE
        ).move_to(UP * 1.6)
        for t in (a_txt, m_txt):
            if t.width > 7.8:
                t.scale_to_fit_width(7.8)

        pts_box = RoundedRectangle(
            corner_radius=0.25,
            width=7.6,
            height=2.5,
            fill_color="#09111E",
            fill_opacity=0.98,
            stroke_color=ACCENT_GOLD,
            stroke_width=3.5,
        ).move_to(DOWN * 0.8)
        pts_hdr = Text("РЕАЛЬНЫЙ СЧЁТ ПО ОЧКАМ", font=FONT, font_size=26, weight="BOLD", color=GRAY_B).move_to(
            pts_box.get_top() + DOWN * 0.45
        )
        pts_val = Text("Алекс: 120   vs   Макс: 99", font=FONT, font_size=44, weight="BOLD", color=ACCENT_MINT).move_to(
            pts_box.get_center() + DOWN * 0.2
        )
        if pts_val.width > 7.0:
            pts_val.scale_to_fit_width(7.0)

        cap = make_caption("Дальние броски снизили %,\nно принесли победу 120 : 99!", y=-4.5)

        self.play(FadeIn(badge), FadeIn(subtitle), run_time=1.2)
        self.play(Write(a_txt), Write(m_txt), run_time=2.0)
        self.play(FadeIn(pts_box), FadeIn(pts_hdr), Write(pts_val), FadeIn(cap, shift=UP * 0.2), run_time=2.0)
        self._pad(total_dur, 5.2)
        self.play(FadeOut(VGroup(badge, subtitle, a_txt, m_txt, pts_box, pts_hdr, pts_val, cap)), run_time=0.4)

    def scene_05_challenge(self, total_dur: float) -> None:
        badge = make_badge("СЕКРЕТ NBA-АНАЛИТИКИ", ACCENT_ORANGE)
        subtitle = make_subtitle("Не верь одному числу!")

        bad = Text("Общий FG%  —  ловушка!", font=FONT, font_size=38, weight="BOLD", color=RED_C).move_to(UP * 2.0)
        good = Text("Смотри: 2P% + 3P% + очки", font=FONT, font_size=36, weight="BOLD", color=ACCENT_MINT).move_to(
            UP * 0.3
        )
        for t in (bad, good):
            if t.width > 7.6:
                t.scale_to_fit_width(7.6)

        cap = make_caption("Проверь статистику в игре:\nоткуда именно бросал игрок?", y=-4.5)

        self.play(FadeIn(badge), FadeIn(subtitle), run_time=1.2)
        self.play(Write(bad), Write(good), FadeIn(cap, shift=UP * 0.2), run_time=1.8)
        self._pad(total_dur, 3.0)
        self.wait(0.3)
