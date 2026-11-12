from datetime import date

import pytest

from nldate import parse

# A Wednesday.
TODAY = date(2025, 11, 12)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("today", date(2025, 11, 12)),
        ("now", date(2025, 11, 12)),
        ("tomorrow", date(2025, 11, 13)),
        ("yesterday", date(2025, 11, 11)),
        ("day after tomorrow", date(2025, 11, 14)),
        ("the day before yesterday", date(2025, 11, 10)),
        ("  TODAY!  ", date(2025, 11, 12)),
    ],
)
def test_keywords(text: str, expected: date) -> None:
    assert parse(text, TODAY) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("tuesday", date(2025, 11, 18)),
        ("wednesday", date(2025, 11, 12)),
        ("this friday", date(2025, 11, 14)),
        ("next tuesday", date(2025, 11, 18)),
        ("next wednesday", date(2025, 11, 19)),
        ("last wednesday", date(2025, 11, 5)),
        ("last friday", date(2025, 11, 7)),
        ("on Mon", date(2025, 11, 17)),
    ],
)
def test_weekdays(text: str, expected: date) -> None:
    assert parse(text, TODAY) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("December 1st, 2025", date(2025, 12, 1)),
        ("dec 1 2025", date(2025, 12, 1)),
        ("1 December 2025", date(2025, 12, 1)),
        ("the 3rd of March, 2024", date(2024, 3, 3)),
        ("2025-12-01", date(2025, 12, 1)),
        ("12/1/2025", date(2025, 12, 1)),
        ("December 1st", date(2025, 12, 1)),
    ],
)
def test_absolute_dates(text: str, expected: date) -> None:
    assert parse(text, TODAY) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("5 days before December 1st, 2025", date(2025, 11, 26)),
        ("1 year and 2 months after yesterday", date(2027, 1, 11)),
        ("two weeks from tomorrow", date(2025, 11, 27)),
        ("in 3 days", date(2025, 11, 15)),
        ("3 days ago", date(2025, 11, 9)),
        ("a week ago", date(2025, 11, 5)),
        ("twenty-one days from now", date(2025, 12, 3)),
        ("2 weeks, 3 days and 1 month after today", date(2025, 12, 29)),
        ("1 week before next tuesday", date(2025, 11, 11)),
        ("2025/12/04", date(2025, 12, 4)),
        ("2025/1/5", date(2025, 1, 5)),
    ],
)
def test_offsets(text: str, expected: date) -> None:
    assert parse(text, TODAY) == expected


def test_month_arithmetic_clamps_to_end_of_month() -> None:
    assert parse("1 month after January 31st, 2025", TODAY) == date(2025, 2, 28)
    assert parse("1 year after February 29, 2024", TODAY) == date(2025, 2, 28)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("next week", date(2025, 11, 19)),
        ("last week", date(2025, 11, 5)),
        ("next month", date(2025, 12, 12)),
        ("next year", date(2026, 11, 12)),
        ("this month", date(2025, 11, 12)),
    ],
)
def test_next_unit(text: str, expected: date) -> None:
    assert parse(text, TODAY) == expected


def test_today_defaults_to_current_date() -> None:
    assert parse("today") == date.today()


@pytest.mark.parametrize(
    "text",
    [
        "",
        "   ",
        "banana",
        "5 days before banana",
        "february 30 2025",
        "13/45/2025",
        "next blursday",
        "3 fortnights ago",
        "99999999999999 days from now",
    ],
)
def test_invalid_input_raises_value_error(text: str) -> None:
    with pytest.raises(ValueError):
        parse(text, TODAY)