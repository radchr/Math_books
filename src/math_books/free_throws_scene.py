"""Two free throws: weighted outcomes, a 100-cell model and the complement rule."""

from fractions import Fraction

from manim import (
    DOWN,
    RED_C,
    RIGHT,
    UP,
    WHITE,
    Cross,
    FadeIn,
    FadeOut,
    Group,
    Line,
    MathTex,
    RoundedRectangle,
    Square,
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
    make_subtitle,
)

configure_vertical_9_16()
MODEL_P = Fraction(7, 10)


def two_shot_outcomes(probability: Fraction) -> dict[str, Fraction]:
    if not 0 <= probability <= 1:
        raise ValueError("Probability must be between zero and one")
    miss = 1 - probability
    return {"ПП": probability**2, "ПМ": probability * miss, "МП": miss * probability, "ММ": miss**2}


def model_grid_outcomes(hit_cells: int) -> list[str]:
    """Each axis has ten equiprobable model cells; the last cells represent misses."""
    if type(hit_cells) is not int or not 0 <= hit_cells <= 10:
        raise ValueError("Hit cells must be an integer from zero to ten")
    return [
        ("П" if row < hit_cells else "М") + ("П" if col < hit_cells else "М") for row in range(10) for col in range(10)
    ]


def fitted_text(label: str, *, size=32, color=WHITE, width=7.2) -> Text:
    text = Text(label, font=FONT, font_size=size, color=color, weight="BOLD")
    if text.width > width:
        text.scale_to_fit_width(width)
    return text


class FreeThrowsBasketball(VerticalShortScene):
    def construct(self) -> None:
        durations = self._load_durations("video_free_throws")
        for segment, key in (
            (self.hook, "01_hook"),
            (self.model, "02_model"),
            (self.misses, "03_misses"),
            (self.complement, "04_complement"),
            (self.challenge, "05_challenge"),
        ):
            self.run_segment(segment, durations[key])

    def finish(self, duration, *, last=False):
        self._pad(duration)
        if last:
            self.wait(0.3)
        else:
            self.play(FadeOut(Group(*self.mobjects)), run_time=0.4)

    def hook(self, duration):
        badge = make_badge("ДВА ШТРАФНЫХ — КАКОЙ ШАНС?")
        title = make_subtitle("Попасть хотя бы один раз")
        balls = VGroup(make_basketball(0.65), make_basketball(0.65)).arrange(RIGHT, buff=1.7).move_to(UP * 2.5)
        percentages = VGroup(
            *[fitted_text("70%", color=ACCENT_CYAN, size=42).next_to(ball, DOWN, buff=0.3) for ball in balls]
        )
        wrong = MathTex(r"70\%+70\%=140\%", font_size=54, color=RED_C).move_to(DOWN * 0.5)
        cross = Cross(wrong, stroke_color=RED_C, stroke_width=5)
        question = fitted_text("Больше 100%? Что-то не так!", size=34, color=ACCENT_GOLD).move_to(DOWN * 2)
        caption = make_caption("Условия модели разберём дальше.\nПросто складывать нельзя!", y=-4.6)
        self.play(FadeIn(badge), FadeIn(title), run_time=1)
        self.play(FadeIn(balls), FadeIn(percentages), run_time=1.1)
        self.play(Write(wrong), run_time=1.3)
        self.play(FadeIn(cross), FadeIn(question), FadeIn(caption), run_time=1)
        self.finish(duration)

    def model(self, duration):
        badge = make_badge("НЕЗАВИСИМЫЕ БРОСКИ", ACCENT_CYAN)
        title = make_subtitle("П — попал • М — мимо")
        root = fitted_text("ДВА БРОСКА", size=28).move_to(UP * 3.8)
        first = VGroup()
        lines = VGroup()
        leaves = VGroup()
        for x, label, color in ((-2, "П: 70%", ACCENT_MINT), (2, "М: 30%", RED_C)):
            node = fitted_text(label, size=30, color=color).move_to([x, 2.35, 0])
            first.add(node)
            lines.add(Line([0, 3.4, 0], [x, 2.65, 0], color=color))
        for index, (outcome, probability) in enumerate(two_shot_outcomes(MODEL_P).items()):
            x = -3 + index * 2
            parent_x = -2 if index < 2 else 2
            color = RED_C if outcome == "ММ" else ACCENT_MINT
            lines.add(Line([parent_x, 2.0, 0], [x, 0.5, 0], color=color))
            branch_label = fitted_text("70%" if index % 2 == 0 else "30%", size=22, color=ACCENT_CYAN)
            branch_label.move_to([(parent_x + x) / 2 + (-0.15 if index % 2 == 0 else 0.15), 1.25, 0])
            card = RoundedRectangle(
                width=1.65, height=1.55, corner_radius=0.16, fill_color=CARD_BG, fill_opacity=1, stroke_color=color
            ).move_to([x, -0.35, 0])
            pair = fitted_text(outcome, size=28, color=color).move_to([x, 0, 0])
            rate = fitted_text(f"{int(probability * 100)}%", size=30, color=ACCENT_GOLD).move_to([x, -0.65, 0])
            leaves.add(VGroup(card, pair, rate, branch_label))
        note = fitted_text("49% + 21% + 21% + 9% = 100%", size=29).move_to(DOWN * 2.1)
        caption = make_caption("После любого первого исхода\nшанс второго попадания — 70%.", y=-4.6)
        self.play(FadeIn(badge), FadeIn(title), FadeIn(root), run_time=1)
        self.play(FadeIn(lines), FadeIn(first), run_time=1.4)
        self.play(FadeIn(leaves, lag_ratio=0.15), run_time=1.8)
        self.play(FadeIn(note), FadeIn(caption), run_time=1)
        self.finish(duration)

    def misses(self, duration):
        badge = make_badge("ПОСЧИТАЕМ ДВА ПРОМАХА", ACCENT_ORANGE)
        title = make_subtitle("100 равновероятных клеток модели")
        cells = VGroup()
        for index, outcome in enumerate(model_grid_outcomes(7)):
            row, col = divmod(index, 10)
            color = RED_C if outcome == "ММ" else ACCENT_MINT
            cell = Square(side_length=0.37, stroke_width=0.8, stroke_color=WHITE, fill_color=color, fill_opacity=0.92)
            cell.move_to([(col - 4.5) * 0.43, 2.0 - (row - 4.5) * 0.43, 0])
            cells.add(cell)
        axis = fitted_text("По 7 частей «попал» и 3 «мимо» на каждой оси", size=23, color=ACCENT_CYAN).move_to(
            DOWN * 0.75
        )
        formula = MathTex(r"0.3\times0.3=0.09=9\%", font_size=48, color=RED_C).move_to(DOWN * 2.05)
        caption = make_caption("Красные: оба мимо — 9 из 100.\nЭто сетка модели, а не серия бросков.", y=-4.6)
        self.play(FadeIn(badge), FadeIn(title), run_time=1)
        self.play(FadeIn(cells, lag_ratio=0.01), run_time=1.8)
        self.play(FadeIn(axis), Write(formula), run_time=1.4)
        self.play(FadeIn(caption), run_time=0.8)
        self.finish(duration)

    def complement(self, duration):
        badge = make_badge("СЧИТАЙ ОТ ОБРАТНОГО", ACCENT_MINT)
        title = make_subtitle("Всё, кроме двух промахов")
        formula = MathTex(r"1-0.3^2=1-0.09=0.91", color=ACCENT_GOLD, font_size=46).move_to(UP * 2.9)
        result = fitted_text("91%", size=100, color=ACCENT_MINT).move_to(UP * 0.8)
        cases = fitted_text("ПП (49%) + ПМ (21%) + МП (21%)", size=27).move_to(DOWN * 1.15)
        distinction = fitted_text("«Хотя бы одно» включает два!", size=33, color=ACCENT_CYAN).move_to(DOWN * 2.3)
        caption = make_caption("Вероятность — часть от целого.\nНельзя получить 140%.", y=-4.6)
        self.play(FadeIn(badge), FadeIn(title), run_time=1)
        self.play(Write(formula), run_time=1.7)
        self.play(FadeIn(result, scale=0.8), run_time=1)
        self.play(FadeIn(cases), FadeIn(distinction), FadeIn(caption), run_time=1.3)
        self.finish(duration)

    def challenge(self, duration):
        badge = make_badge("ТВОЙ ХОД!", ACCENT_ORANGE)
        title = make_subtitle("Теперь точность каждого — 80%")
        balls = VGroup(make_basketball(0.5), make_basketball(0.5)).arrange(RIGHT, buff=1).move_to(UP * 2.8)
        question = fitted_text("Хотя бы одно за два броска?", size=35, color=ACCENT_GOLD).move_to(UP * 1)
        hint = fitted_text("1. Два промаха\n2. Вычти их шанс из 100%", size=31, color=ACCENT_CYAN).move_to(DOWN * 0.6)
        answer = MathTex(r"1-0.2^2=0.96=96\%", font_size=47, color=ACCENT_MINT).move_to(DOWN * 2.3)
        caption = make_caption("Независимые броски, постоянная точность.\nРасчёт модели — не гарантия.", y=-4.6)
        self.play(FadeIn(badge), FadeIn(title), FadeIn(balls), run_time=1.1)
        self.play(FadeIn(question), FadeIn(hint), FadeIn(caption), run_time=1.4)
        elapsed = self.renderer.time - self._segment_start
        reveal_at = self.word_timestamp("05_challenge", "ответ", fallback=duration * 0.72, after_s=elapsed + 0.5)
        self.wait(max(0.0, float(reveal_at) - elapsed))
        self.play(Write(answer), run_time=1)
        self.finish(duration, last=True)
