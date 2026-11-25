"""Conservative multilingual transcript comparison, not pronunciation certification."""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from fractions import Fraction
from functools import lru_cache

import pymorphy3
import snowballstemmer
from num2words import num2words

from math_books.languages import validate_language
from math_books.multilingual_numbers import normalize as normalize_multilingual


@lru_cache(maxsize=1)
def _morphology():
    return pymorphy3.MorphAnalyzer(), snowballstemmer.stemmer("russian")


@lru_cache(maxsize=8192)
def _lemma(word: str) -> str:
    for parsed in _morphology()[0].parse(word):
        if parsed.tag.POS == "NUMR" or "Anum" in parsed.tag:
            return parsed.normal_form.replace("ё", "е")
    return _morphology()[0].parse(word)[0].normal_form.replace("ё", "е")


@lru_cache(maxsize=1)
def _number_words() -> dict[str, int]:
    values = {}
    for value in [*range(20), *range(20, 100, 10), *range(100, 1000, 100)]:
        for kind in ("cardinal", "ordinal"):
            word = num2words(value, lang="ru", to=kind)
            if " " not in word:
                values[_lemma(word)] = value
    values.update(тысяча=1000, миллион=1_000_000, миллиард=1_000_000_000)
    return values


def _integer_at(words: list[str], start: int) -> tuple[int, int]:
    values = _number_words()
    total = group = 0
    last_rank, last_scale, last_value = 4, float("inf"), None
    index = start
    had_group = False
    while index < len(words) and words[index] in values:
        value = values[words[index]]
        if value >= 1000:
            if value >= last_scale:
                break
            total += (group if had_group else 1) * value
            group, had_group, last_rank, last_scale = 0, False, 4, value
        else:
            rank = 3 if value >= 100 else 2 if value >= 10 else 1
            # Never conflate a repeated number with a valid compound numeral.
            if rank >= last_rank or (last_value is not None and 10 <= last_value < 20 and rank == 1):
                break
            group += value
            had_group, last_rank = True, rank
        last_value = value
        index += 1
    return total + group, index


def normalize_spoken_text(text: str, language: str = "ru") -> list[str]:
    """Normalize forms, percentages and equivalent Russian decimal/fraction numbers."""
    validate_language(language)
    if not isinstance(text, str):
        raise ValueError("Transcript and expected narration must be strings")
    if language != "ru":
        return normalize_multilingual(text, language)
    text = unicodedata.normalize("NFKC", text).lower().replace("ё", "е").replace("%", " процентов ")
    for symbol, spoken in (
        (">=", "больше равно"),
        ("<=", "меньше равно"),
        ("≥", "больше равно"),
        ("≤", "меньше равно"),
        (">", "больше"),
        ("<", "меньше"),
        ("=", "равно"),
    ):
        text = text.replace(symbol, f" {spoken} ")
    text = re.sub(
        r"\b(двух|трех)очков[а-я]*\b",
        lambda m: "2 очковый" if m.group(1) == "двух" else "3 очковый",
        text,
    )
    text = re.sub(r"\bтрячк[а-я]*\b", "3 очка", text)
    text = re.sub(r"\bдвачк[а-я]*\b", "2 очка", text)
    text = re.sub(r"\b([1-9]0)-х\b", lambda m: f"{int(m.group(1)) // 10} десятых", text)
    text = re.sub(r"\bсут(ых|ые|ая|ой|ую)\b", r"сот\1", text)
    text = re.sub(r"\bбрас(ок|ка|ку|ком|ке|ки|ков|кам|ками|ках)\b", r"брос\1", text)
    text = text.replace("+", " плюс ").replace("−", " минус ").replace("×", " умножить ")
    for symbol, spoken in (
        ("-", "минус"),
        ("*", "умножить"),
        ("⋅", "умножить"),
        ("·", "умножить"),
        ("/", "разделить"),
        ("÷", "разделить"),
    ):
        text = text.replace(symbol, f" {spoken} ")

    def spell(match):
        number = match.group().replace(",", ".")
        if len(number) > 30:
            raise ValueError("Unsupported oversized numeral in transcript")
        return " " + num2words(number, lang="ru") + " "

    text = re.sub(r"\d+(?:[.,]\d+)?", spell, text)
    words = [_lemma(word) for word in re.findall(r"[а-яa-z]+", text)]
    denominators = {
        "десятый": 10,
        "сотый": 100,
        "тысячный": 1000,
        "десятитысячный": 10_000,
        "стотысячный": 100_000,
        "миллионный": 1_000_000,
    }
    tokens = []
    index = 0
    while index < len(words):
        if words[index] not in _number_words():
            tokens.append(_morphology()[1].stemWord(words[index]))
            index += 1
            continue
        value, end = _integer_at(words, index)
        number = Fraction(value)
        if end < len(words) and words[end] == "целый":
            numerator_start = end + 1
            if numerator_start < len(words) and words[numerator_start] == "и":
                numerator_start += 1
            numerator, fraction_end = _integer_at(words, numerator_start)
            if fraction_end > numerator_start and fraction_end < len(words) and words[fraction_end] in denominators:
                number += Fraction(numerator, denominators[words[fraction_end]])
                end = fraction_end + 1
        elif (
            end + 1 < len(words)
            and words[end] == "и"
            and _integer_at(words, end + 1)[1] > end + 1
            and _integer_at(words, end + 1)[1] < len(words)
            and words[_integer_at(words, end + 1)[1]] in denominators
        ):
            numerator, fraction_end = _integer_at(words, end + 1)
            number += Fraction(numerator, denominators[words[fraction_end]])
            end = fraction_end + 1
        elif end < len(words) and words[end] in denominators:
            number /= denominators[words[end]]
            end += 1
        tokens.append(f"#number:{number}")
        index = end
    return tokens


@lru_cache(maxsize=3)
def _protected_words(language: str = "ru") -> set[str]:
    # These bounded vocabularies deliberately list inflections rather than
    # deriving semantic equivalence from spelling similarity. A tiny typo in
    # a unit, condition or negation must still request review.
    if language == "en":
        return set(
            (
                "not no nor neither without independent dependent independence dependence exactly at least most "
                "minimum maximum more less greater fewer equal equals equalities inequality inequalities "
                "always never possible impossible before after until unless if then otherwise only except instead "
                "above below under over within between all any each every none both either probability probabilities "
                "chance chances average mean median sum total angle angles triangle triangles half third quarter "
                "percent percentage percentages point points percentagepoint shot shots attempt attempts hit hits "
                "miss misses meter meters metre metres centimeter centimeters centimetre centimetres kilometer "
                "kilometers kilometre kilometres millimeter millimeters millimetre millimetres second seconds "
                "minute minutes hour hours degree degrees kilogram kilograms gram grams dollar dollars euro euros "
                "pound pounds year years ruble rubles hryvnia hryvnias cm mm km m s kg g plus minus multiply divided "
                "division multiplication addition subtraction guaranteed guarantee guarantees certain uncertain "
                "conditional unconditional positive negative increase decreases decrease increases true false "
                "in on at into onto inside outside near far parallel perpendicular through along across "
                "millisecond milliseconds microsecond microseconds nanosecond nanoseconds "
                "micrometer micrometers micrometre micrometres nanometer nanometers nanometre nanometres "
                "ms ns us μs µs hz khz mhz ghz volt volts watt watts joule joules newton newtons"
            ).split()
        )
    if language == "uk":
        return set(
            (
                "не ні немає без незалежний незалежна незалежне незалежні незалежних незалежності "
                "залежний залежна залежне залежні залежних залежності рівно точно хоча щонайменше щонайбільше "
                "мінімум максимум більше менше більший менший більша менша більші менші дорівнює рівний рівні "
                "завжди ніколи можливий можлива можливе можливі неможливий неможлива неможливе неможливі "
                "до після перед якщо коли доки поки інакше лише тільки крім замість понад нижче вище між "
                "кожен кожна кожне кожні будь всі усі жоден жодна обидва обидві хоча б найменше найбільше "
                "ймовірність ймовірності імовірність імовірності шанс шанси шансів середній середня середнє середні "
                "сума суми кут кути кутів трикутник трикутники трикутника половина половини третина чверть "
                "відсоток відсотка відсотки відсотків відсотковий пункт пункти пунктів очко очки очок "
                "кидок кидки кидків кидка спроба спроби спроб попадання попадань промах промахи промахів "
                "метр метра метри метрів сантиметр сантиметри сантиметрів міліметр міліметри міліметрів "
                "кілометр кілометри кілометрів секунда секунди секунд хвилина хвилини хвилин година години годин "
                "градус градуси градусів кілограм кілограми кілограмів грам грами грамів гривня гривні гривень "
                "долар долари доларів євро рубль рублі рублів рік роки років см мм км м с кг г "
                "гарантія гарантовано гарантує гарантований додатний від'ємний зростає зменшується істина хиба "
                "на під над всередині зовні біля поруч через уздовж вздовж "
                "паралельний паралельна паралельне паралельні перпендикулярний перпендикулярна перпендикулярне "
                "перпендикулярні мілісекунда мілісекунди мілісекунд мікросекунда мікросекунди мікросекунд "
                "наносекунда наносекунди наносекунд мікрометр мікрометри мікрометрів нанометр нанометри нанометрів "
                "мс нс мкс гц кгц мгц ггц вольт вольти вольтів ват вати ватів джоуль джоулі джоулів "
                "ньютон ньютони ньютонів"
            ).split()
        )
    words = (
        "равно не нет ни без независимый зависимый ровно хотя минимум максимум больше меньше всегда никогда "
        "возможный невозможный до после перед от только кроме вместо плюс минус умножить вычесть разделить "
        "процент пункт очко атака бросок попадание промах метр секунда градус рубль год раз клетка серия "
        "половина треть четверть средний сумма угол треугольник орел решка вероятность шанс доля исход переход "
        "если иначе пока когда каждый любой все никакой оба"
    )
    return {_morphology()[1].stemWord(_lemma(word)) for word in words.split()}


def _alignment(expected: list[str], actual: list[str]) -> list[dict]:
    distances = [[0] * (len(actual) + 1) for _ in range(len(expected) + 1)]
    for i in range(len(expected) + 1):
        distances[i][0] = i
    for j in range(len(actual) + 1):
        distances[0][j] = j
    for i, word in enumerate(expected, 1):
        for j, observed in enumerate(actual, 1):
            distances[i][j] = min(
                distances[i - 1][j] + 1, distances[i][j - 1] + 1, distances[i - 1][j - 1] + (word != observed)
            )
    edits = []
    i, j = len(expected), len(actual)
    while i or j:
        if i and j and distances[i][j] == distances[i - 1][j - 1] + (expected[i - 1] != actual[j - 1]):
            if expected[i - 1] != actual[j - 1]:
                edits.append({"kind": "substitution", "expected": expected[i - 1], "actual": actual[j - 1]})
            i, j = i - 1, j - 1
        elif j and distances[i][j] == distances[i][j - 1] + 1:
            edits.append({"kind": "insertion", "actual": actual[j - 1]})
            j -= 1
        else:
            edits.append({"kind": "deletion", "expected": expected[i - 1]})
            i -= 1
    return edits[::-1]


def compare_transcript(expected_text: str, transcript: str, language: str = "ru") -> dict:
    """Reject additions/deletions and protected changes; tolerate only tiny ASR substitutions."""
    expected, actual = normalize_spoken_text(expected_text, language), normalize_spoken_text(transcript, language)
    edits = _alignment(expected, actual)
    insertions = sum(edit["kind"] == "insertion" for edit in edits)
    deletions = sum(edit["kind"] == "deletion" for edit in edits)
    substitutions = sum(edit["kind"] == "substitution" for edit in edits)
    wer = len(edits) / max(1, len(expected))
    known_latin = set(re.findall(r"[a-z]+", expected_text.lower()))
    foreign = (
        sorted(set(re.findall(r"[а-яёіїєґ]+", transcript.lower())))
        if language == "en"
        else sorted(set(re.findall(r"[a-z]+", transcript.lower())) - known_latin)
    )

    def protected(tokens):
        vocabulary = _protected_words(language)
        return [
            token
            for token in tokens
            if token.startswith("#") or token in vocabulary or (len(token) == 1 and token.isalpha())
        ]

    issues = []
    if not expected or not actual:
        issues.append("Empty expected text or unintelligible/empty transcript")
    if foreign:
        issues.append(f"Unexpected foreign words: {', '.join(foreign)}")
    if protected(expected) != protected(actual):
        issues.append("Numbers, units, negation or scientific qualifiers do not match")
    if insertions or deletions:
        issues.append(f"Extra/missing speech: {insertions} inserted and {deletions} deleted tokens")
    similar = all(
        (language == "ru" and len(edit["expected"]) <= 2 and len(edit["actual"]) <= 2)
        or SequenceMatcher(None, edit["expected"], edit["actual"]).ratio() >= 0.8
        for edit in edits
        if edit["kind"] == "substitution"
    )
    if substitutions > 2 or wer > 0.10 or not similar:
        issues.append(f"Transcript mismatch exceeds conservative ASR tolerance ({wer:.1%})")
    warnings = (
        ["Minor noncritical ASR substitution; inspect the reported difference"] if substitutions and not issues else []
    )
    return {
        "ok": not issues,
        "issues": issues,
        "warnings": warnings,
        "foreign_words": foreign,
        "insertions": insertions,
        "deletions": deletions,
        "substitutions": substitutions,
        "word_error_rate": round(wer, 4),
        "edits": edits,
        "expected_tokens": expected,
        "actual_tokens": actual,
    }
