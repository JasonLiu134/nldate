"""Pattern-matching parser for natural-language dates.

Supported inputs (case-insensitive):

* Keywords: ``today``, ``now``, ``tomorrow``, ``yesterday``,
  ``day after tomorrow``, ``the day before yesterday``
* Weekdays: ``tuesday``, ``this tuesday``, ``next tuesday``, ``last tuesday``
  (``next``/``last`` are strictly after/before today; a bare or ``this``
  weekday is the first such day on or after today)
* ``next|last|this week|month|year``
* Absolute dates: ``December 1st, 2025``, ``Dec 1 2025``, ``1 December 2025``,
  ``2025-12-01``, ``12/1/2025``. A missing year means the year of ``today``.
* Offsets: ``in 3 days``, ``3 days ago``, ``2 weeks from now``,
  ``5 days before <date>``, ``1 year and 2 months after <date>``.
  Numbers may be digits, ``a``/``an``, or words up to ninety-nine.

Month arithmetic clamps to the end of the month (Jan 31 + 1 month = Feb 28).
Anything unrecognized raises ``ValueError``.
"""

from __future__ import annotations

import calendar
import re
from datetime import date, timedelta

_MONTHS = {
    "january": 1,
    "jan": 1,
    "february": 2,
    "feb": 2,
    "march": 3,
    "mar": 3,
    "april": 4,
    "apr": 4,
    "may": 5,
    "june": 6,
    "jun": 6,
    "july": 7,
    "jul": 7,
    "august": 8,
    "aug": 8,
    "september": 9,
    "sept": 9,
    "sep": 9,
    "october": 10,
    "oct": 10,
    "november": 11,
    "nov": 11,
    "december": 12,
    "dec": 12,
}

_WEEKDAYS = {
    "monday": 0,
    "mon": 0,
    "tuesday": 1,
    "tues": 1,
    "tue": 1,
    "wednesday": 2,
    "wed": 2,
    "thursday": 3,
    "thurs": 3,
    "thur": 3,
    "thu": 3,
    "friday": 4,
    "fri": 4,
    "saturday": 5,
    "sat": 5,
    "sunday": 6,
    "sun": 6,
}

_ONES = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
}

_TENS = {
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}


def _alternation(words: dict[str, int]) -> str:
    return "|".join(sorted(words, key=len, reverse=True))


_MONTH_RE = _alternation(_MONTHS)
_WEEKDAY_RE = _alternation(_WEEKDAYS)

_DURATION_SPLIT = re.compile(r",\s*(?:and\s+)?|\s+and\s+")
_DURATION_PART = re.compile(r"(.+?) (days?|weeks?|months?|years?)")
_DAY_AROUND = re.compile(r"(?:the )?day (before|after) (.+)")
_RELATIVE_TO = re.compile(r"(.+?) (before|after|from) (.+)")
_NEXT_UNIT = re.compile(r"(next|last|this) (week|month|year)")
_WEEKDAY = re.compile(rf"(?:(next|last|this) )?({_WEEKDAY_RE})")
_ISO = re.compile(r"(\d{4})-(\d{1,2})-(\d{1,2})")
_SLASH = re.compile(r"(\d{1,2})/(\d{1,2})(?:/(\d{4}))?")
_MONTH_FIRST = re.compile(
    rf"({_MONTH_RE})\.? (\d{{1,2}})(?:st|nd|rd|th)?(?:,? (\d{{4}}))?"
)
_DAY_FIRST = re.compile(
    rf"(\d{{1,2}})(?:st|nd|rd|th)?(?: of)? ({_MONTH_RE})\.?(?:,? (\d{{4}}))?"
)

# An offset is (months, days); years are folded into months, weeks into days.
_Offset = tuple[int, int]


def _normalize(s: str) -> str:
    text = " ".join(s.lower().split()).rstrip(".!?")
    if text.startswith("on "):
        text = text[3:]
    return text


def _parse_number(text: str) -> int | None:
    if re.fullmatch(r"\d+", text):
        return int(text)
    if text in ("a", "an"):
        return 1
    parts = text.replace("-", " ").split()
    if len(parts) == 1:
        word = parts[0]
        if word in _ONES:
            return _ONES[word]
        if word in _TENS:
            return _TENS[word]
    elif len(parts) == 2:
        tens, ones = parts
        if tens in _TENS and ones in _ONES and 1 <= _ONES[ones] <= 9:
            return _TENS[tens] + _ONES[ones]
    return None


def _parse_duration(text: str) -> _Offset | None:
    months = 0
    days = 0
    for part in _DURATION_SPLIT.split(text):
        match = _DURATION_PART.fullmatch(part.strip())
        if match is None:
            return None
        n = _parse_number(match.group(1))
        if n is None:
            return None
        unit = match.group(2).rstrip("s")
        if unit == "day":
            days += n
        elif unit == "week":
            days += 7 * n
        elif unit == "month":
            months += n
        else:
            months += 12 * n
    return months, days


def _add_months(d: date, n: int) -> date:
    year, month0 = divmod(d.year * 12 + d.month - 1 + n, 12)
    month = month0 + 1
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(d.day, last_day))


def _apply(base: date, offset: _Offset, sign: int) -> date:
    months, days = offset
    return _add_months(base, sign * months) + timedelta(days=sign * days)


def _parse_weekday(qualifier: str | None, name: str, today: date) -> date:
    target = _WEEKDAYS[name]
    if qualifier == "last":
        back = (today.weekday() - target) % 7 or 7
        return today - timedelta(days=back)
    forward = (target - today.weekday()) % 7
    if qualifier == "next":
        forward = forward or 7
    return today + timedelta(days=forward)


def _parse_absolute(text: str, today: date) -> date | None:
    match = _ISO.fullmatch(text)
    if match:
        return date(int(match[1]), int(match[2]), int(match[3]))

    match = _SLASH.fullmatch(text)
    if match:
        year = int(match[3]) if match[3] else today.year
        return date(year, int(match[1]), int(match[2]))

    match = _MONTH_FIRST.fullmatch(text)
    if match:
        year = int(match[3]) if match[3] else today.year
        return date(year, _MONTHS[match[1]], int(match[2]))

    match = _DAY_FIRST.fullmatch(text)
    if match:
        year = int(match[3]) if match[3] else today.year
        return date(year, _MONTHS[match[2]], int(match[1]))

    return None


def _parse_base(text: str, today: date) -> date | None:
    if text in ("today", "now"):
        return today
    if text == "tomorrow":
        return today + timedelta(days=1)
    if text == "yesterday":
        return today - timedelta(days=1)

    match = _NEXT_UNIT.fullmatch(text)
    if match:
        sign = {"next": 1, "last": -1, "this": 0}[match[1]]
        unit = match[2]
        if unit == "week":
            return today + timedelta(weeks=sign)
        return _add_months(today, sign * (12 if unit == "year" else 1))

    match = _WEEKDAY.fullmatch(text)
    if match:
        return _parse_weekday(match[1], match[2], today)

    return _parse_absolute(text, today)


def _parse_expr(text: str, today: date) -> date | None:
    if text.startswith("in "):
        offset = _parse_duration(text[3:])
        return None if offset is None else _apply(today, offset, 1)

    if text.endswith(" ago"):
        offset = _parse_duration(text[: -len(" ago")])
        return None if offset is None else _apply(today, offset, -1)

    if text.endswith(" from now"):
        offset = _parse_duration(text[: -len(" from now")])
        return None if offset is None else _apply(today, offset, 1)

    match = _DAY_AROUND.fullmatch(text)
    if match:
        base = _parse_expr(match[2], today)
        if base is not None:
            return base + timedelta(days=1 if match[1] == "after" else -1)

    match = _RELATIVE_TO.fullmatch(text)
    if match:
        offset = _parse_duration(match[1])
        base = _parse_expr(match[3], today)
        if offset is not None and base is not None:
            return _apply(base, offset, -1 if match[2] == "before" else 1)

    return _parse_base(text, today)


def parse(s: str, today: date | None = None) -> date:
    """Convert a natural-language date string to a ``datetime.date``.

    Args:
        s: The text to parse, e.g. ``"5 days before December 1st, 2025"``.
        today: Reference date for relative expressions. Defaults to
            ``date.today()``.

    Raises:
        ValueError: If ``s`` is not a recognized date expression.
    """
    if today is None:
        today = date.today()
    text = _normalize(s)
    try:
        result = _parse_expr(text, today) if text else None
    except OverflowError as exc:  # absurdly large offsets
        raise ValueError(f"date out of range: {s!r}") from exc
    if result is None:
        raise ValueError(f"unrecognized date expression: {s!r}")
    return result