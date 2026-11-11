"""
Тести парсера розкладу САЗ (FR-004) на анонімізованій фікстурі fixtures/saz/schedule_preview.html,
що повторює структуру справжньої сторінки my.ukma.edu.ua/schedule/preview/...

Примітка щодо використання ШІ: тести згенеровано ШІ (Claude), переглянуто автором PR.
"""

import time as time_module
from datetime import time
from pathlib import Path

import pytest

from api.services.saz_parser import (
    MAX_WEEK,
    SazParseError,
    parse_room,
    parse_schedule,
    parse_weeks,
    split_subject_and_teacher,
)

pytestmark = pytest.mark.req("FR-004")

FIXTURE = Path(__file__).parent.parent / "fixtures" / "saz" / "schedule_preview.html"


@pytest.fixture(scope="module")
def schedule():
    return parse_schedule(FIXTURE.read_text(encoding="utf-8"))


def test_specialty_and_year_are_read_from_page_header(schedule):
    assert schedule.specialty == "Тестова інженерія"
    assert schedule.year == 3


def test_empty_slots_and_unparsable_rows_are_skipped(schedule):
    # 8 рядків із дисципліною: 1 порожній слот пропущено, 1 з нерозпізнаними тижнями - у попередження
    assert len(schedule.entries) == 6
    assert schedule.warnings == ["Рядок 15: Не вдалося розпізнати тижні: за потреби"]


def test_day_and_time_merged_with_rowspan_apply_to_following_rows(schedule):
    # Arrange: «Вівторок» і «10:00-11:20» об'єднано на кілька рядків
    tuesday_ten = [e for e in schedule.entries if e.weekday == 1 and e.start == time(10, 0)]

    # Assert
    assert [e.group for e in tuesday_ten] == ["лекція", "2"]
    assert all(e.end == time(11, 20) for e in tuesday_ten)


def test_entry_contains_subject_teacher_group_weeks_and_room(schedule):
    first = schedule.entries[0]

    assert (first.weekday, first.start, first.end) == (0, time(8, 30), time(9, 50))
    assert first.subject == "Алгоритми"
    assert first.teacher == "А.А. Альфа"
    assert first.group == "лекція"
    assert first.weeks == (2, 3, 4)
    assert first.room == ("1", "223")


@pytest.mark.parametrize(
    "cell,expected",
    [
        ("Функціональне програмування, доц. В.С. Проценко", ("Функціональне програмування", "В.С. Проценко")),
        ("Алгоритми, ст.викл.Б.Бета", ("Алгоритми", "Б. Бета")),
        ("Бази даних, cт.викл. В.В. Гамма", ("Бази даних", "В.В. Гамма")),  # латинська «c» у званні
        ("Розробка інтерфейсу (UI/UX), ст. викл.О.В. Тест", ("Розробка інтерфейсу (UI/UX)", "О.В. Тест")),
        ("Курсова робота", ("Курсова робота", "")),
    ],
)
def test_subject_and_teacher_are_split_despite_typos_in_titles(cell, expected):
    assert split_subject_and_teacher(cell) == expected


@pytest.mark.parametrize(
    "text,expected",
    [("2-4", (2, 3, 4)), ("2,4", (2, 4)), ("1, 3-5", (1, 3, 4, 5)), ("7", (7,))],
)
def test_weeks_are_parsed_from_ranges_and_lists(text, expected):
    assert parse_weeks(text) == expected


@pytest.mark.parametrize("text", ["за потреби", "", "5-2"])
def test_invalid_weeks_are_rejected(text):
    with pytest.raises(ValueError):
        parse_weeks(text)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("1-223", (("1", "223"), False)),
        ("1-225 /онлайн", (("1", "225"), False)),
        ("1-309онлайн", (("1", "309"), False)),
        ("1-310/Б", (("1", "310"), False)),
        ("Дистанційно", (None, True)),
        ("10к", (None, False)),
    ],
)
def test_room_formats_from_saz_are_recognized(text, expected):
    assert parse_room(text) == expected


def test_page_without_schedule_table_is_rejected():
    with pytest.raises(SazParseError):
        parse_schedule("<html><body><h1>Увійдіть, щоб переглянути розклад</h1></body></html>")


# --- REL-H04: некоректні rowspan / colspan ---

FIXTURE_HTML = FIXTURE.read_text(encoding="utf-8")


@pytest.mark.req("REL-002")
@pytest.mark.parametrize("attribute", ["rowspan", "colspan"])
@pytest.mark.parametrize("value", ["abc", "-1", "0", "2.5", "1000000"])
def test_invalid_span_rejects_page_with_clear_parse_error(attribute, value):
    # Arrange: перша клітинка з таким атрибутом отримує некоректне значення
    original = f'{attribute}="4"' if attribute == "colspan" else 'rowspan="2"'
    html = FIXTURE_HTML.replace(original, f'{attribute}="{value}"', 1)
    assert html != FIXTURE_HTML

    # Act / Assert: SazParseError (а не сирий ValueError з int() і не роздута сітка)
    with pytest.raises(SazParseError, match=f"Некоректний атрибут {attribute}"):
        parse_schedule(html)


@pytest.mark.req("REL-002")
def test_span_with_spaces_and_upper_limit_is_accepted():
    # Arrange: пробіли довкола числа й межове значення дозволені
    html = FIXTURE_HTML.replace('rowspan="2"', 'rowspan=" 2 "', 1).replace('colspan="6"', 'colspan="20"', 1)

    # Act
    result = parse_schedule(html)

    # Assert
    assert result.entries


# --- REL-H06: номери тижнів поза межами семестру ---


@pytest.mark.req("REL-002")
@pytest.mark.parametrize("text", ["1-1000000", "1-31", "31", "0", "0-3", "5-100000", "1, 3-999999999"])
def test_weeks_outside_semester_are_rejected_without_heavy_work(text):
    # Arrange
    started = time_module.perf_counter()

    # Act / Assert: відмова ще до побудови range(), тож без «прокручування» мільйона значень
    with pytest.raises(ValueError, match="поза межами"):
        parse_weeks(text)
    assert time_module.perf_counter() - started < 0.5


@pytest.mark.req("REL-002")
@pytest.mark.parametrize(
    "text,expected",
    [("1", (1,)), (str(MAX_WEEK), (MAX_WEEK,)), (f"1-{MAX_WEEK}", tuple(range(1, MAX_WEEK + 1)))],
)
def test_weeks_on_the_boundary_are_accepted(text, expected):
    assert parse_weeks(text) == expected


@pytest.mark.req("REL-002")
def test_row_with_out_of_range_weeks_becomes_warning_and_other_rows_are_kept():
    # Arrange: у першому рядку фікстури тижні «2-4» замінюємо на нереальний діапазон
    html = FIXTURE_HTML.replace("2-4", "1-1000000", 1)
    assert html != FIXTURE_HTML

    # Act
    result = parse_schedule(html)

    # Assert: проблемний рядок пропущено з попередженням, решту розкладу імпортовано
    assert any("поза межами" in warning for warning in result.warnings)
    assert result.entries
