"""Vertical (9:16) Manim animation: Buzzer-Beater Math — One 3-Pointer vs Quick-2 Chain."""

from __future__ import annotations

from fractions import Fraction

from manim import (
    DOWN,
    GRAY_B,
    LEFT,
    RED_C,
    RIGHT,
    UP,
    WHITE,
    Arrow,
    Create,
    FadeIn,
    FadeOut,
    Group,
    Line,
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
    CARD_BG,
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

DIRECT_THREE_PROB = Fraction(3, 10)
CHAIN_STEP_PROBS = (Fraction(7, 10), Fraction(1, 2), Fraction(7, 10))
CHALLENGE_STEP_PROBS = (Fraction(4, 5), Fraction(4, 5), Fraction(4, 5))
BAR_FULL_SCALE_HEIGHT = 10.333333333333334


def chain_success_probability(steps: tuple[Fraction, ...]) -> Fraction:
    """Compute joint probability of independent sequential steps."""
    if not steps:
        raise ValueError("Chain must contain at least one step")
    product = Fraction(1, 1)
    for prob in steps:
        if not 0 <= prob <= 1:
            raise ValueError(f"Step probability out of bounds: {prob}")
        product *= prob
    return product


def format_decimal(prob: Fraction) -> str:
    """Format an exact rational probability as a clean terminating decimal."""
    val = float(prob)
    return f"{val:.3f}".rstrip("0").rstrip(".")


def format_percent(prob: Fraction) -> str:
    """Format an exact rational probability as a clean percentage string (e.g. '30%', '24.5%')."""
    pct = float(prob * 100)
    if pct.is_integer():
        return f"{int(pct)}%"
    return f"{pct:.2f}".rstrip("0").rstrip(".") + "%"


def build_buzzer_visual_spec(
    direct_prob: Fraction = DIRECT_THREE_PROB,
    chain_steps: tuple[Fraction, ...] = CHAIN_STEP_PROBS,
    challenge_steps: tuple[Fraction, ...] = CHALLENGE_STEP_PROBS,
) -> dict[str, object]:
    """Derive all scene text, formulas, and bar heights directly from model probabilities."""
    if not 0 <= direct_prob <= 1:
        raise ValueError(f"Direct probability out of bounds: {direct_prob}")
    if len(chain_steps) != 3 or len(challenge_steps) != 3:
        raise ValueError("Buzzer visual layout requires exactly 3 steps in chain_steps and challenge_steps")

    chain_prob = chain_success_probability(chain_steps)
    challenge_prob = chain_success_probability(challenge_steps)
    direct_pct = format_percent(direct_prob)
    direct_miss_pct = format_percent(1 - direct_prob)
    chain_pct = format_percent(chain_prob)
    challenge_pct = format_percent(challenge_prob)
    step_pcts = tuple(format_percent(s) for s in chain_steps)
    min_step_pct = format_percent(min(chain_steps))
    step_decs = r" \times ".join(format_decimal(s) for s in chain_steps)
    chain_dec = format_decimal(chain_prob)
    chain_pct_num = chain_pct.removesuffix("%")

    ch_prod_dec = format_decimal(challenge_prob)
    ch_pct_num = challenge_pct.removesuffix("%")
    ch_step_pcts = tuple(format_percent(s) for s in challenge_steps)
    if len(set(challenge_steps)) == 1:
        ch_step = challenge_steps[0]
        ch_dec = format_decimal(ch_step)
        challenge_step_pct = format_percent(ch_step)
        challenge_title = f"Цепочка из 3 шагов по {challenge_step_pct}"
        challenge_question = f"Каждый из 3 шагов — {challenge_step_pct}.\nКаков общий шанс всей цепочки?"
        challenge_hint = f"Умножь {ch_dec} три раза подряд:\n" + " × ".join(format_decimal(s) for s in challenge_steps)
        challenge_latex = rf"{ch_dec}^{len(challenge_steps)} = {ch_prod_dec} = {ch_pct_num}\%"
    else:
        challenge_step_pct = ", ".join(ch_step_pcts)
        challenge_title = f"Цепочка: {' • '.join(ch_step_pcts)}"
        challenge_question = f"Шаги: {', '.join(ch_step_pcts)}.\nКаков общий шанс всей цепочки?"
        challenge_hint = "Перемножь вероятности всех шагов:\n" + " × ".join(format_decimal(s) for s in challenge_steps)
        ch_decs_latex = r" \times ".join(format_decimal(s) for s in challenge_steps)
        challenge_latex = rf"{ch_decs_latex} = {ch_prod_dec} = {ch_pct_num}\%"

    bar_a_height = round(float(direct_prob) * BAR_FULL_SCALE_HEIGHT, 3)
    bar_b_height = round(float(chain_prob) * BAR_FULL_SCALE_HEIGHT, 3)
    if direct_prob > chain_prob:
        verdict_cmp = ">"
        verdict_conclusion = "Прямая трёха выгоднее!"
    elif direct_prob < chain_prob:
        verdict_cmp = "<"
        verdict_conclusion = "Цепочка из 3 шагов выгоднее!"
    else:
        verdict_cmp = "="
        verdict_conclusion = "Шансы обоих планов равны!"

    return {
        "direct_pct": direct_pct,
        "direct_miss_pct": direct_miss_pct,
        "step_pcts": step_pcts,
        "min_step_pct": min_step_pct,
        "chain_pct": chain_pct,
        "challenge_step_pct": challenge_step_pct,
        "challenge_title": challenge_title,
        "challenge_question": challenge_question,
        "challenge_pct": challenge_pct,
        "multiply_latex": rf"{step_decs} = {chain_dec} = {chain_pct_num}\%",
        "challenge_hint": challenge_hint,
        "challenge_latex": challenge_latex,
        "bar_a_height": bar_a_height,
        "bar_b_height": bar_b_height,
        "verdict_text": f"{direct_pct}  {verdict_cmp}  {chain_pct}  •  {verdict_conclusion}",
    }


def fitted_text(label: str, *, size: int = 32, color: str = WHITE, width: float = 7.4) -> Text:
    text = Text(label, font=FONT, font_size=size, color=color, weight="BOLD", line_spacing=1.2)
    if text.width > width:
        text.scale_to_fit_width(width)
    return text


class BuzzerBeaterBasketball(VerticalShortScene):
    """Vertical 9:16 short comparing a single 3-point shot with a 3-step quick-2 + foul chain."""

    def construct(self) -> None:
        self.spec = build_buzzer_visual_spec()
        durations = self._load_durations("videos/video_buzzer")
        for segment, key in (
            (self.hook, "01_hook"),
            (self.three_shot, "02_three_shot"),
            (self.chain_plan, "03_chain_plan"),
            (self.multiply, "04_multiply"),
            (self.challenge, "05_challenge"),
        ):
            self.run_segment(segment, durations[key])

    def finish(self, duration: float, *, last: bool = False) -> None:
        self._pad(duration)
        if last:
            self.wait(0.3)
        else:
            self.play(FadeOut(Group(*self.mobjects)), run_time=0.4)

    def hook(self, duration: float) -> None:
        badge = make_badge("10 СЕКУНД ДО СИРЕНЫ!", ACCENT_ORANGE)
        title = make_subtitle("Минус 3 очка • Что выбрать?")
        board = make_scoreboard("78 : 81", "10.0 СЕК • −3 ОЧКА", y=2.55)

        plan_a = RoundedRectangle(
            width=3.55, height=1.95, corner_radius=0.22, fill_color=CARD_BG, fill_opacity=0.95, stroke_color=ACCENT_MINT
        ).move_to([-1.95, -0.35, 0])
        txt_a = (
            VGroup(
                fitted_text("ПЛАН А", size=28, color=ACCENT_MINT, width=3.1),
                fitted_text("Сразу бросить +3", size=24, color=WHITE, width=3.1),
            )
            .arrange(DOWN, buff=0.22)
            .move_to(plan_a.get_center())
        )

        plan_b = RoundedRectangle(
            width=3.55, height=1.95, corner_radius=0.22, fill_color=CARD_BG, fill_opacity=0.95, stroke_color=ACCENT_CYAN
        ).move_to([1.95, -0.35, 0])
        txt_b = (
            VGroup(
                fitted_text("ПЛАН Б", size=28, color=ACCENT_CYAN, width=3.1),
                fitted_text("Быстрые +2 и фол", size=24, color=WHITE, width=3.1),
            )
            .arrange(DOWN, buff=0.22)
            .move_to(plan_b.get_center())
        )

        question = fitted_text("Один сложный шаг или три простых?", size=32, color=ACCENT_GOLD).move_to(DOWN * 2.25)
        caption = make_caption("Математика помогает тренеру\nвыбрать лучший план в концовке!", y=-4.6)

        self.play(FadeIn(badge), FadeIn(title), FadeIn(board), run_time=1.2)
        self.play(FadeIn(plan_a), FadeIn(txt_a), FadeIn(plan_b), FadeIn(txt_b), run_time=1.5)
        self.play(Write(question), FadeIn(caption), run_time=1.2)
        self.finish(duration)

    def three_shot(self, duration: float) -> None:
        direct_pct = str(self.spec["direct_pct"])
        miss_pct = str(self.spec["direct_miss_pct"])
        badge = make_badge("ПЛАН А • ПРЯМАЯ ТРЁХА", ACCENT_MINT)
        title = make_subtitle("Один бросок через защиту")

        ball = make_basketball(0.75).move_to(UP * 2.75)
        pct = fitted_text(direct_pct, size=88, color=ACCENT_MINT).move_to(UP * 0.85)
        sub = fitted_text(f"1 шаг = сразу {direct_pct} на спасение", size=32, color=ACCENT_GOLD).move_to(DOWN * 0.55)

        outcomes = RoundedRectangle(
            width=7.4, height=1.85, corner_radius=0.22, fill_color=CARD_BG, fill_opacity=0.95, stroke_color=ACCENT_MINT
        ).move_to(DOWN * 2.15)
        out_txt = (
            VGroup(
                fitted_text(f"Попал ({direct_pct})  →  Ничья и овертайм", size=27, color=ACCENT_MINT, width=6.8),
                fitted_text(f"Мимо ({miss_pct})   →  Матч окончен", size=27, color=RED_C, width=6.8),
            )
            .arrange(DOWN, buff=0.25)
            .move_to(outcomes.get_center())
        )

        caption = make_caption("Считаем в модели.\nОдин трудный бросок решает всё.", y=-4.6)

        self.play(FadeIn(badge), FadeIn(title), FadeIn(ball), run_time=1.1)
        self.play(FadeIn(pct, scale=0.85), Write(sub), run_time=1.4)
        self.play(FadeIn(outcomes), FadeIn(out_txt), FadeIn(caption), run_time=1.4)
        self.finish(duration)

    def chain_plan(self, duration: float) -> None:
        s1_pct, s2_pct, s3_pct = self.spec["step_pcts"]
        badge = make_badge("ПЛАН Б • ЦЕПОЧКА ИЗ 3 ШАГОВ", ACCENT_CYAN)
        title = make_subtitle("Каждый шаг кажется проще!")

        steps_data = (
            ("1. Быстрые 2 очка", s1_pct, ACCENT_MINT, 2.7),
            ("2. Промах соперника с фола", s2_pct, ACCENT_GOLD, 0.7),
            ("3. Вторая атака на 2 очка", s3_pct, ACCENT_CYAN, -1.3),
        )
        cards = VGroup()
        arrows = VGroup()
        for idx, (label, rate, color, y_pos) in enumerate(steps_data):
            box = RoundedRectangle(
                width=7.4, height=1.25, corner_radius=0.2, fill_color=CARD_BG, fill_opacity=0.95, stroke_color=color
            ).move_to([0, y_pos, 0])
            l_txt = fitted_text(label, size=27, color=WHITE, width=5.1).move_to(box.get_left() + RIGHT * 2.8)
            r_txt = fitted_text(rate, size=38, color=color, width=1.6).move_to(box.get_right() + LEFT * 0.95)
            cards.add(VGroup(box, l_txt, r_txt))
            if idx < 2:
                arrows.add(
                    Arrow(
                        [0, y_pos - 0.65, 0],
                        [0, y_pos - 1.35, 0],
                        buff=0.05,
                        color=GRAY_B,
                        stroke_width=4,
                    )
                )

        note = fitted_text(
            f"Все три числа ≥ {self.spec['min_step_pct']}! Выглядит надёжно?", size=29, color=ACCENT_GOLD
        ).move_to(DOWN * 2.65)
        caption = make_caption("Чтобы план сработал, должны\nвыполниться ВСЕ ТРИ шага подряд.", y=-4.6)

        self.play(FadeIn(badge), FadeIn(title), run_time=1.0)
        self.play(FadeIn(cards, lag_ratio=0.2), Create(arrows), run_time=2.2)
        self.play(Write(note), FadeIn(caption), run_time=1.3)
        self.finish(duration)

    def multiply(self, duration: float) -> None:
        badge = make_badge("ЛОВУШКА УМНОЖЕНИЯ", ACCENT_ORANGE)
        title = make_subtitle("Вероятности шагов перемножаются")

        formula = MathTex(str(self.spec["multiply_latex"]), font_size=44, color=ACCENT_GOLD).move_to(UP * 3.1)
        if formula.width > 7.6:
            formula.scale_to_fit_width(7.6)

        base_y = -1.6
        axis = Line(LEFT * 3.3, RIGHT * 3.3, color=GRAY_B, stroke_width=3).move_to([0, base_y, 0])

        h_a = float(self.spec["bar_a_height"])
        h_b = float(self.spec["bar_b_height"])
        bar_a = RoundedRectangle(
            width=2.3, height=h_a, corner_radius=0.16, fill_color=ACCENT_MINT, fill_opacity=0.92, stroke_color=WHITE
        ).move_to([-1.7, base_y + h_a / 2, 0])
        val_a = fitted_text(str(self.spec["direct_pct"]), size=42, color="#0D1B2A").move_to(bar_a.get_center())
        lbl_a = fitted_text("План А (1 трёха)", size=24, color=ACCENT_MINT).next_to(bar_a, DOWN, buff=0.25)

        bar_b = RoundedRectangle(
            width=2.3, height=h_b, corner_radius=0.16, fill_color=RED_C, fill_opacity=0.88, stroke_color=WHITE
        ).move_to([1.7, base_y + h_b / 2, 0])
        val_b = fitted_text(str(self.spec["chain_pct"]), size=38, color=WHITE).move_to(bar_b.get_center())
        lbl_b = fitted_text("План Б (3 шага)", size=24, color=RED_C).next_to(bar_b, DOWN, buff=0.25)

        verdict = fitted_text(str(self.spec["verdict_text"]), size=30, color=ACCENT_MINT).move_to(DOWN * 2.8)
        caption = make_caption("Каждый новый шаг в цепочке\nотрезает часть общего шанса!", y=-4.6)

        self.play(FadeIn(badge), FadeIn(title), Write(formula), run_time=1.6)
        self.play(Create(axis), FadeIn(bar_a), FadeIn(val_a), FadeIn(lbl_a), run_time=1.4)
        self.play(FadeIn(bar_b), FadeIn(val_b), FadeIn(lbl_b), run_time=1.4)
        self.play(Write(verdict), FadeIn(caption), run_time=1.3)
        self.finish(duration)

    def challenge(self, duration: float) -> None:
        badge = make_badge("ТВОЙ ХОД!", ACCENT_ORANGE)
        title = make_subtitle(str(self.spec["challenge_title"]))

        balls = (
            VGroup(make_basketball(0.45), make_basketball(0.45), make_basketball(0.45))
            .arrange(RIGHT, buff=0.85)
            .move_to(UP * 2.85)
        )
        question = fitted_text(str(self.spec["challenge_question"]), size=33, color=ACCENT_GOLD)
        question.move_to(UP * 1.05)
        hint = fitted_text(str(self.spec["challenge_hint"]), size=30, color=ACCENT_CYAN).move_to(DOWN * 0.65)
        answer = MathTex(str(self.spec["challenge_latex"]), font_size=48, color=ACCENT_MINT).move_to(DOWN * 2.3)
        caption = make_caption("Независимые шаги в модели.\nРасчёт помогает выбрать план!", y=-4.6)

        self.play(FadeIn(badge), FadeIn(title), FadeIn(balls), run_time=1.1)
        self.play(FadeIn(question), FadeIn(hint), FadeIn(caption), run_time=1.4)
        elapsed = self.renderer.time - self._segment_start
        self.wait(max(0, duration * 0.68 - elapsed))
        self.play(Write(answer), run_time=1.0)
        self.finish(duration, last=True)
