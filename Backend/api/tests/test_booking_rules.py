import re
from datetime import datetime, timedelta, timezone

import pytest

from api.booking_rules import BookingRuleError, booking_duration, validate_attendees_fit_room

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


@pytest.mark.parametrize("attendees,capacity", [(30, 30), (29, 30), (1, 1), (1, 30)])
def test_attendees_within_capacity_are_accepted(attendees, capacity):
    validate_attendees_fit_room(attendees, capacity)  # 30 з 30 вбиває мутант `>` -> `>=`


@pytest.mark.parametrize("attendees,capacity", [(31, 30), (2, 1)])
def test_attendees_over_capacity_are_rejected(attendees, capacity):
    assert_raises_message(MSG_OVER_CAPACITY, validate_attendees_fit_room, attendees, capacity)


@pytest.mark.parametrize("attendees", [0, -1])
def test_attendees_below_one_are_rejected(attendees):
    assert_raises_message(MSG_ATTENDEES_MIN, validate_attendees_fit_room, attendees, 30)


@pytest.mark.parametrize("capacity", [0, -5])
def test_capacity_below_one_is_rejected(capacity):
    assert_raises_message(MSG_CAPACITY_MIN, validate_attendees_fit_room, 1, capacity)


def test_duration_of_regular_lesson():
    start = datetime(2026, 10, 21, 10, 0, tzinfo=UTC)
    end = datetime(2026, 10, 21, 11, 20, tzinfo=UTC)
    assert booking_duration(start, end) == timedelta(hours=1, minutes=20)


def test_duration_of_one_second_is_positive():
    start = datetime(2026, 10, 21, 10, 0, tzinfo=UTC)
    assert booking_duration(start, start + timedelta(seconds=1)) == timedelta(seconds=1)


@pytest.mark.parametrize("delta", [timedelta(0), timedelta(seconds=-1)])
def test_duration_rejects_end_not_after_start(delta):
    start = datetime(2026, 10, 21, 10, 0, tzinfo=UTC)
    assert_raises_message(MSG_END_BEFORE_START, booking_duration, start, start + delta)


def test_duration_rejects_naive_start():
    naive = datetime(2026, 10, 21, 10, 0)
    aware = datetime(2026, 10, 21, 11, 0, tzinfo=UTC)
    assert_raises_message(MSG_NAIVE, booking_duration, naive, aware)


def test_duration_rejects_naive_end():
    naive = datetime(2026, 10, 21, 11, 0)
    aware = datetime(2026, 10, 21, 10, 0, tzinfo=UTC)
    assert_raises_message(MSG_NAIVE, booking_duration, aware, naive)


def test_duration_uses_real_elapsed_time_across_dst_change():
    from zoneinfo import ZoneInfo

    kyiv = ZoneInfo("Europe/Kyiv")
    # 25.10.2026 годинник переводять назад: ніч на годину довша (8 год, а не 7).
    start = datetime(2026, 10, 24, 23, 0, tzinfo=kyiv)
    end = datetime(2026, 10, 25, 6, 0, tzinfo=kyiv)
    assert booking_duration(start, end) == timedelta(hours=8)
