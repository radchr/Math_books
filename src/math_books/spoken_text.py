"""Conservative Russian transcript comparison, not pronunciation certification."""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from fractions import Fraction
from functools import lru_cache

import pymorphy3
import snowballstemmer
from num2words import num2words


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


def normalize_spoken_text(text: str) -> list[str]:
    """Normalize forms, percentages and equivalent Russian decimal/fraction numbers."""
    if not isinstance(text, str):
        raise ValueError("Transcript and expected narration must be strings")
    text = unicodedata.normalize("NFKC", text).lower().replace("ё", "е").replace("%", " процентов ")
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
    text = re.sub(r"-(?=\s*\d)", " минус ", text)

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


@lru_cache(maxsize=1)
def _protected_words() -> set[str]:
    words = (
        "не нет ни без независимый зависимый ровно хотя минимум максимум больше меньше всегда никогда "
        "возможный невозможный до после перед от только кроме вместо плюс минус умножить вычесть разделить "
        "процент пункт очко атака бросок попадание промах метр секунда градус рубль год раз клетка серия "
        "половина треть четверть средний сумма угол треугольник орел решка вероятность шанс доля исход переход"
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


def compare_transcript(expected_text: str, transcript: str) -> dict:
    """Reject additions/deletions and protected changes; tolerate only tiny ASR substitutions."""
    expected, actual = normalize_spoken_text(expected_text), normalize_spoken_text(transcript)
    edits = _alignment(expected, actual)
    insertions = sum(edit["kind"] == "insertion" for edit in edits)
    deletions = sum(edit["kind"] == "deletion" for edit in edits)
    substitutions = sum(edit["kind"] == "substitution" for edit in edits)
    wer = len(edits) / max(1, len(expected))
    known_latin = set(re.findall(r"[a-z]+", expected_text.lower()))
    foreign = sorted(set(re.findall(r"[a-z]+", transcript.lower())) - known_latin)

    def protected(tokens):
        return [token for token in tokens if token.startswith("#number:") or token in _protected_words()]

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
        (len(edit["expected"]) <= 2 and len(edit["actual"]) <= 2)
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
