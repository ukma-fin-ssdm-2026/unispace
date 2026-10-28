"""
Тести модуля room_occupancy.

Тести працюють без підключення до бази даних за допомогою тестових дублерів Mock.

Примітка щодо використання ШІ: тести згенеровано з допомогою ШІ
та верифіковано локальним запуском pytest людиною (Тимохина Ксенія).
"""

from datetime import date, datetime
from unittest.mock import Mock, patch

import pytest
from api.room_occupancy import get_day_bookings, get_previous_booking


def make_booking(booking_id, room_id, start_str, end_str, user_id=1):
    """Створює дублер об'єкта Booking."""
    return Mock(
        id=booking_id,
        room_id=room_id,
        user_id=user_id,
        start_time=datetime.fromisoformat(start_str),
        end_time=datetime.fromisoformat(end_str),
    )


@pytest.mark.req("FR-019")
def test_get_day_bookings_queries_correct_parameters_from_db():
    booking_first = make_booking(1, 101, "2026-10-28 08:30:00", "2026-10-28 10:05:00")
    booking_second = make_booking(2, 101, "2026-10-28 10:25:00", "2026-10-28 12:00:00")
    target_date = date(2026, 10, 28)

    with patch("api.room_occupancy.Booking.objects") as mock_objects:
        mock_qs = mock_objects.filter.return_value
        mock_qs.order_by.return_value = [booking_first, booking_second]

        results = get_day_bookings(room_id=101, target_date=target_date)

        assert results == [booking_first, booking_second]
        mock_objects.filter.assert_called_once_with(
            room_id=101,
            start_time__date=target_date,
        )
        mock_qs.order_by.assert_called_once_with("start_time")


@pytest.mark.req("FR-019")
def test_first_pair_of_the_day_returns_none():
    current = make_booking(1, room_id=101, start_str="2026-10-28 08:30:00", end_str="2026-10-28 10:05:00")
    day_bookings = [current]

    previous = get_previous_booking(current, day_bookings)

    assert previous is None


@pytest.mark.req("FR-019")
def test_consecutive_pair_with_break_returns_preceding_booking():
    first_pair = make_booking(1, room_id=101, start_str="2026-10-28 08:30:00", end_str="2026-10-28 10:05:00")
    second_pair = make_booking(2, room_id=101, start_str="2026-10-28 10:25:00", end_str="2026-10-28 12:00:00")
    day_bookings = [first_pair, second_pair]

    previous = get_previous_booking(second_pair, day_bookings)

    assert previous == first_pair


@pytest.mark.req("FR-019")
def test_back_to_back_bookings_without_break_returns_preceding_booking():
    pair_a = make_booking(1, room_id=101, start_str="2026-10-28 12:00:00", end_str="2026-10-28 13:30:00")
    pair_b = make_booking(2, room_id=101, start_str="2026-10-28 13:30:00", end_str="2026-10-28 15:00:00")

    previous = get_previous_booking(pair_b, [pair_a, pair_b])

    assert previous == pair_a


@pytest.mark.req("FR-019")
def test_booking_after_window_returns_latest_booking_before_window():
    morning_pair = make_booking(1, room_id=101, start_str="2026-10-28 08:30:00", end_str="2026-10-28 10:05:00")
    afternoon_pair = make_booking(2, room_id=101, start_str="2026-10-28 14:15:00", end_str="2026-10-28 15:50:00")

    previous = get_previous_booking(afternoon_pair, [morning_pair, afternoon_pair])

    assert previous == morning_pair


@pytest.mark.req("FR-019")
def test_multiple_prior_bookings_returns_only_the_most_recent_one():
    pair_1 = make_booking(1, room_id=101, start_str="2026-10-28 08:30:00", end_str="2026-10-28 10:05:00")
    pair_2 = make_booking(2, room_id=101, start_str="2026-10-28 10:25:00", end_str="2026-10-28 12:00:00")
    pair_3 = make_booking(3, room_id=101, start_str="2026-10-28 12:20:00", end_str="2026-10-28 13:55:00")

    previous = get_previous_booking(pair_3, [pair_1, pair_2, pair_3])

    assert previous == pair_2


@pytest.mark.req("FR-019")
def test_bookings_in_other_rooms_are_ignored():
    other_room = make_booking(1, room_id=102, start_str="2026-10-28 08:30:00", end_str="2026-10-28 10:05:00")
    target_room = make_booking(2, room_id=101, start_str="2026-10-28 10:25:00", end_str="2026-10-28 12:00:00")

    previous = get_previous_booking(target_room, [other_room, target_room])

    assert previous is None


@pytest.mark.req("FR-019")
def test_bookings_from_previous_days_are_ignored():
    yesterday = make_booking(1, room_id=101, start_str="2026-10-27 18:00:00", end_str="2026-10-27 19:35:00")
    today = make_booking(2, room_id=101, start_str="2026-10-28 10:25:00", end_str="2026-10-28 12:00:00")

    previous = get_previous_booking(today, [yesterday, today])

    assert previous is None


@pytest.mark.req("FR-019")
def test_future_bookings_are_ignored():
    current = make_booking(1, room_id=101, start_str="2026-10-28 10:25:00", end_str="2026-10-28 12:00:00")
    later_pair = make_booking(2, room_id=101, start_str="2026-10-28 14:15:00", end_str="2026-10-28 15:50:00")

    previous = get_previous_booking(current, [current, later_pair])

    assert previous is None


@pytest.mark.req("FR-019")
def test_get_previous_booking_fetches_from_db_when_day_bookings_is_none():
    first_pair = make_booking(1, 101, "2026-10-28 08:30:00", "2026-10-28 10:05:00")
    current_pair = make_booking(2, 101, "2026-10-28 10:25:00", "2026-10-28 12:00:00")

    with patch("api.room_occupancy.get_day_bookings") as mock_fetch:
        mock_fetch.return_value = [first_pair, current_pair]

        previous = get_previous_booking(current_pair)

        assert previous == first_pair
        mock_fetch.assert_called_once_with(101, date(2026, 10, 28))
