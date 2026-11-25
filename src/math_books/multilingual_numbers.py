"""Exact, deliberately bounded Ukrainian/English number grammar.

Unsupported constructions remain literal tokens and therefore cannot silently pass
as an equivalent numeric value. No Russian morphology is used here.
"""

import re
import unicodedata
from fractions import Fraction
from functools import lru_cache

from num2words import num2words


def _clean(text: str) -> str:
    return unicodedata.normalize("NFKC", text).lower().translate(str.maketrans({"’": "'", "ʼ": "'", "‘": "'"}))


@lru_cache(maxsize=2)
def vocabulary(language: str) -> dict[str, int]:
    result = {}
    for value in [*range(20), *range(20, 100, 10), *range(100, 1000, 100)]:
        word = _clean(num2words(value, lang=language))
        if " " not in word and "-" not in word:
            result[word] = value
    if language == "uk":
        groups = {
            0: "нуль нуля нулю нулем",
            1: "один одна одне одну одного однієї одній одним",
            2: "два дві двох двом двома",
            3: "три трьох трьом трьома",
            4: "чотири чотирьох чотирьом чотирма",
            5: "п'ять п'яти п'ятьох п'ятьма",
            6: "шість шести шістьох шістьма",
            7: "сім семи сімох сімома",
            8: "вісім восьми вісьмох вісьмома",
            9: "дев'ять дев'яти дев'ятьох дев'ятьма",
            10: "десять десяти десятьох десятьма",
            20: "двадцять двадцяти",
            30: "тридцять тридцяти",
            40: "сорок сорока",
            50: "п'ятдесят п'ятдесяти",
            60: "шістдесят шістдесяти",
            70: "сімдесят сімдесяти",
            80: "вісімдесят вісімдесяти",
            90: "дев'яносто дев'яноста",
            100: "сто ста",
            1000: "тисяча тисячі тисяч тисячу",
            1000000: "мільйон мільйони мільйонів",
        }
        for value, forms in groups.items():
            result.update(dict.fromkeys(forms.split(), value))
        for value in range(11, 20):
            result[_clean(num2words(value, lang="uk"))[:-1] + "и"] = value
    else:
        result.update(hundred=100, thousand=1000, million=1000000, billion=1000000000)
    return result


def integer_at(words: list[str], start: int, language: str) -> tuple[int, int]:
    values = vocabulary(language)
    total = group = 0
    rank = 4
    last = None
    scale = float("inf")
    index = start
    while index < len(words):
        word = words[index]
        if word == "and" and language == "en" and group >= 100 and index + 1 < len(words):
            next_value = values.get(words[index + 1], -1)
            if 0 < next_value < 100 and rank == 3:
                index += 1
                continue
        if word not in values:
            break
        value = values[word]
        if language == "en" and word == "hundred":
            if not 1 <= group <= 9 or rank != 1:
                break
            group *= 100
            rank = 3
        elif value >= 1000:
            if value >= scale:
                break
            total += (group or 1) * value
            group, rank, scale = 0, 4, value
        else:
            next_rank = 3 if value >= 100 else 2 if value >= 10 else 1
            if next_rank >= rank or (last is not None and 10 <= last < 20 and next_rank == 1):
                break
            group += value
            rank = next_rank
        last = value
        index += 1
    return total + group, index


DENOMINATORS = {
    "en": {
        "half": 2,
        "halves": 2,
        "third": 3,
        "thirds": 3,
        "quarter": 4,
        "quarters": 4,
        "fourth": 4,
        "fourths": 4,
        "tenth": 10,
        "tenths": 10,
        "hundredth": 100,
        "hundredths": 100,
        "thousandth": 1000,
        "thousandths": 1000,
    },
    "uk": {
        "друга": 2,
        "других": 2,
        "третя": 3,
        "третіх": 3,
        "четверта": 4,
        "четвертих": 4,
        "десята": 10,
        "десяту": 10,
        "десятих": 10,
        "сота": 100,
        "соту": 100,
        "сотих": 100,
        "тисячна": 1000,
        "тисячну": 1000,
        "тисячних": 1000,
        "десятитисячних": 10000,
        "стотисячних": 100000,
        "мільйонних": 1000000,
    },
}


def normalize(text: str, language: str) -> list[str]:
    text = _clean(text).replace("⁄", "/").replace("∕", "/")
    if language == "en":
        text = text.replace("won't", "will not").replace("can't", "can not").replace("cannot", "can not")
        text = re.sub(r"\b([a-z]+)n't\b", r"\1 not", text)
        text = re.sub(r"\bper\s+cent\b", "percent", text)
        # Only cardinal-number hyphens are separators; other hyphens stay
        # visible so an arithmetic minus can never disappear.
        text = re.sub(
            r"\b(twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety)-"
            r"(one|two|three|four|five|six|seven|eight|nine)\b",
            r"\1 \2",
            text,
        )
    operation_words = (
        {
            "plus": "#plus",
            "minus": "#minus",
            "times": "#multiply",
            "multiplied by": "#multiply",
            "divided by": "#divide",
            "equals": "#eq",
        }
        if language == "en"
        else {
            "плюс": "#plus",
            "мінус": "#minus",
            "помножити на": "#multiply",
            "помножено на": "#multiply",
            "поділити на": "#divide",
            "поділено на": "#divide",
            "дорівнює": "#eq",
        }
    )
    for phrase, token in operation_words.items():
        text = re.sub(r"\b" + phrase + r"\b", f" {token} ", text)
    # An adjacent digit/digit slash is a numeric fraction. A spaced slash,
    # or a slash next to a spelled-out operand, is an explicit division.
    text = re.sub(r"(?<!\d)/|/(?!\d)", " #divide ", text)
    percent = "percent" if language == "en" else "відсоток"
    text = text.replace("%", f" {percent} ")
    for symbol, token in [
        (">=", "#ge"),
        ("<=", "#le"),
        ("≥", "#ge"),
        ("≤", "#le"),
        (">", "#gt"),
        ("<", "#lt"),
        ("=", "#eq"),
        ("+", "#plus"),
        ("−", "#minus"),
        ("×", "#multiply"),
        ("*", "#multiply"),
        ("⋅", "#multiply"),
        ("·", "#multiply"),
        ("-", "#minus"),
        ("÷", "#divide"),
    ]:
        text = text.replace(symbol, f" {token} ")
    words = re.findall(r"#[a-z]+|\d+(?:[.,]\d+)?(?:/\d+)?|[^\W\d_]+(?:'[^\W\d_]+)*", text)
    standalone = (
        {"half": 2, "quarter": 4}
        if language == "en"
        else {"половина": 2, "половини": 2, "половину": 2, "третина": 3, "чверть": 4}
    )
    tokens = []
    index = 0
    denominators = DENOMINATORS[language]
    while index < len(words):
        word = words[index]
        if word[0].isdigit():
            if len(word) > 100:
                raise ValueError("Unsupported oversized numeral in transcript")
            try:
                value = Fraction(word.replace(",", "."))
            except (ValueError, ZeroDivisionError):
                raise ValueError("Invalid numeric fraction") from None
            tokens.append(f"#number:{value}")
            index += 1
            continue
        value, end = integer_at(words, index, language)
        if end == index:
            if word in standalone:
                tokens.append(f"#number:{Fraction(1, standalone[word])}")
                index += 1
                continue
            aliases = {
                "відсотків": "відсоток",
                "відсотки": "відсоток",
                "процентів": "відсоток",
                "проценти": "відсоток",
                "процент": "відсоток",
                "percents": "percent",
            }
            tokens.append(aliases.get(word, word))
            index += 1
            continue
        number = Fraction(value)
        if language == "en" and end < len(words) and words[end] == "point":
            position = end + 1
            digits = []
            while position < len(words) and words[position] in vocabulary(language):
                digit = vocabulary(language)[words[position]]
                if digit > 9:
                    break
                digits.append(str(digit))
                position += 1
            if digits:
                number += Fraction(int("".join(digits)), 10 ** len(digits))
                end = position
        elif (
            language == "en"
            and end + 2 < len(words)
            and words[end : end + 2] == ["and", "a"]
            and words[end + 2] in standalone
        ):
            number += Fraction(1, standalone[words[end + 2]])
            end += 3
        elif end < len(words) and words[end] in denominators:
            number /= denominators[words[end]]
            end += 1
        elif language == "uk" and end < len(words) and words[end] in ("ціла", "цілу", "цілих", "ціле", "цілі"):
            start = end + 1
            if start < len(words) and words[start] in ("і", "й"):
                start += 1
            numerator, fraction_end = integer_at(words, start, language)
            if fraction_end > start and fraction_end < len(words) and words[fraction_end] in denominators:
                number += Fraction(numerator, denominators[words[fraction_end]])
                end = fraction_end + 1
        tokens.append(f"#number:{number}")
        index = end
    return tokens
