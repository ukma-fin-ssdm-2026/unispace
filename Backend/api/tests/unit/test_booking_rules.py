"""
Тести доменних правил бронювання, перевірок тривалості та місткості.
Цей модуль об'єднує тести для консолідованої бізнес-логіки.

Примітка щодо використання ШІ: модуль утворено шляхом рефакторингу та
об'єднання розпорошених тестів (з test_utils.py, test_validators.py та
старого test_booking_rules.py) в єдиний тестовий шар за допомогою ШІ-асистента.
"""

import re
from datetime import datetime, timedelta, timezone, time

import pytest

from api.services.booking_rules import (
    BookingRuleError,
    booking_duration,
    is_recently_changed,
    validate_attendees_fit_room,
    is_valid_lesson_duration,
)

UTC = timezone.utc

MSG_NAIVE = "Час бронювання має містити часовий пояс."
MSG_END_BEFORE_START = "Час завершення має бути пізніше за час початку."
MSG_ATTENDEES_MIN = "Кількість учасників має бути не меншою за 1."
MSG_CAPACITY_MIN = "Місткість аудиторії має бути не меншою за 1."
MSG_OVER_CAPACITY = "Кількість учасників перевищує місткість аудиторії."


def assert_raises_message(message, func, *args):
    """Перевіряє тип помилки і ПОВНИЙ текст повідомлення (а не підрядок)."""
    with pytest.raises(BookingRuleError, match=f"^{re.escape(message)}$"):
        func(*args)

    # ==========================================
    # Тести тривалості (booking_duration)
    # ==========================================


@pytest.mark.req("US-03")
def test_duration_of_regular_lesson():
    start = datetime(2026, 10, 21, 10, 0, tzinfo=UTC)
    end = datetime(2026, 10, 21, 11, 20, tzinfo=UTC)
    assert booking_duration(start, end) == timedelta(hours=1, minutes=20)


@pytest.mark.req("US-03")
def test_duration_of_one_second_is_positive():
    start = datetime(2026, 10, 21, 10, 0, tzinfo=UTC)
    assert booking_duration(start, start + timedelta(seconds=1)) == timedelta(seconds=1)


@pytest.mark.req("US-03")
@pytest.mark.parametrize("delta", [timedelta(0), timedelta(seconds=-1)])
def test_duration_rejects_end_not_after_start(delta):
    start = datetime(2026, 10, 21, 10, 0, tzinfo=UTC)
    assert_raises_message(MSG_END_BEFORE_START, booking_duration, start, start + delta)


@pytest.mark.req("US-03")
def test_duration_rejects_naive_start():
    naive = datetime(2026, 10, 21, 10, 0)
    aware = datetime(2026, 10, 21, 11, 0, tzinfo=UTC)
    assert_raises_message(MSG_NAIVE, booking_duration, naive, aware)


@pytest.mark.req("US-03")
def test_duration_rejects_naive_end():
    naive = datetime(2026, 10, 21, 11, 0)
    aware = datetime(2026, 10, 21, 10, 0, tzinfo=UTC)
    assert_raises_message(MSG_NAIVE, booking_duration, aware, naive)


@pytest.mark.req("US-03")
def test_duration_uses_real_elapsed_time_across_dst_change():
    from zoneinfo import ZoneInfo

    kyiv = ZoneInfo("Europe/Kyiv")
    # 25.10.2026 годинник переводять назад: ніч на годину довша (8 год, а не 7).
    start = datetime(2026, 10, 24, 23, 0, tzinfo=kyiv)
    end = datetime(2026, 10, 25, 6, 0, tzinfo=kyiv)
    assert booking_duration(start, end) == timedelta(hours=8)

    # ==========================================
    # Тести тривалості пари (is_valid_lesson_duration) - З test_validators.py
    # ==========================================


@pytest.mark.req("US-03")
def test_inverted_times_returns_false():
    start = time(10, 30)
    end = time(9, 0)
    assert is_valid_lesson_duration(start, end) is False


@pytest.mark.req("US-03")
def test_duration_exceeds_limit_returns_false():
    start = time(10, 0)
    end = time(12, 0)
    assert is_valid_lesson_duration(start, end) is False

    # ==========================================
    # Тести нещодавніх змін (is_recently_changed)
    # ==========================================


LESSON_START = datetime(2026, 10, 21, 10, 0, tzinfo=UTC)


@pytest.mark.req("US-05")
def test_change_within_24_hours_before_start_is_recent():
    assert is_recently_changed([LESSON_START - timedelta(hours=23, minutes=59)], LESSON_START) is True


@pytest.mark.req("US-05")
def test_change_exactly_24_hours_before_start_is_not_recent():
    assert is_recently_changed([LESSON_START - timedelta(hours=24)], LESSON_START) is False


@pytest.mark.req("US-05")
def test_change_earlier_than_24_hours_is_not_recent():
    assert is_recently_changed([LESSON_START - timedelta(days=3)], LESSON_START) is False


@pytest.mark.req("US-05")
def test_change_at_lesson_start_is_recent():
    assert is_recently_changed([LESSON_START], LESSON_START) is True


@pytest.mark.req("US-05")
def test_change_after_lesson_start_is_not_recent():
    assert is_recently_changed([LESSON_START + timedelta(minutes=1)], LESSON_START) is False


@pytest.mark.req("US-05")
def test_no_changes_is_not_recent():
    assert is_recently_changed([], LESSON_START) is False


@pytest.mark.req("US-05")
def test_one_recent_change_among_old_ones_is_recent():
    changes = [LESSON_START - timedelta(days=5), LESSON_START - timedelta(hours=2)]
    assert is_recently_changed(changes, LESSON_START) is True


@pytest.mark.req("US-05")
def test_recent_change_rejects_naive_lesson_start():
    assert_raises_message(MSG_NAIVE, is_recently_changed, [], datetime(2026, 10, 21, 10, 0))

    # ==========================================
    # Тести місткості (validate_attendees_fit_room)
    # ==========================================


@pytest.mark.req("US-10")
@pytest.mark.parametrize("attendees,capacity", [(30, 30), (29, 30), (1, 1), (1, 30)])
def test_attendees_within_capacity_are_accepted(attendees, capacity):
    validate_attendees_fit_room(attendees, capacity)  # 30 з 30 вбиває мутант `>` -> `>=`


@pytest.mark.req("US-10")
@pytest.mark.parametrize("attendees,capacity", [(31, 30), (2, 1)])
def test_attendees_over_capacity_are_rejected(attendees, capacity):
    assert_raises_message(MSG_OVER_CAPACITY, validate_attendees_fit_room, attendees, capacity)


@pytest.mark.req("US-10")
@pytest.mark.parametrize("attendees", [0, -1])
def test_attendees_below_one_are_rejected(attendees):
    assert_raises_message(MSG_ATTENDEES_MIN, validate_attendees_fit_room, attendees, 30)


@pytest.mark.req("US-10")
@pytest.mark.parametrize("capacity", [0, -5])
def test_capacity_below_one_is_rejected(capacity):
    assert_raises_message(MSG_CAPACITY_MIN, validate_attendees_fit_room, 1, capacity)
