"""
REL-001: якщо PostgreSQL перериває одночасне бронювання як deadlock чи serialization failure,
сервіс повертає конфлікт (409), а не 500. Детерміновано відтворює збій, який зрідка дає
test_concurrent_bookings.py на справжніх паралельних запитах.

Примітка щодо використання ШІ: тести згенеровано ШІ (Claude), переглянуто автором PR.
"""

from unittest.mock import patch

import pytest
from django.db import OperationalError

from api.services.bookings import BookingConflictError, change_booking_room, create_booking

from .conftest import at

pytestmark = [pytest.mark.django_db, pytest.mark.req("REL-001")]


class _PgError(Exception):
    def __init__(self, sqlstate):
        super().__init__(sqlstate)
        self.sqlstate = sqlstate


def db_error(sqlstate):
    """OperationalError Django з причиною від драйвера psycopg (у неї є sqlstate)."""
    error = OperationalError("database error")
    error.__cause__ = _PgError(sqlstate)
    return error


@pytest.mark.parametrize("sqlstate", ["40P01", "40001"])
def test_deadlock_or_serialization_failure_on_create_is_a_conflict(teacher, room, make_lesson, sqlstate):
    lesson = make_lesson(at(10), at(11, 30))

    with patch("api.services.bookings.Booking.objects.create", side_effect=db_error(sqlstate)):
        with pytest.raises(BookingConflictError):
            create_booking(lesson, room, teacher)


def test_deadlock_on_room_change_is_a_conflict(teacher, other_room, make_booking):
    booking = make_booking(at(10), at(11, 30))

    with patch.object(type(booking), "save", side_effect=db_error("40P01")):
        with pytest.raises(BookingConflictError):
            change_booking_room(booking, other_room, "", teacher)


def test_other_database_errors_are_not_hidden(teacher, room, make_lesson):
    lesson = make_lesson(at(10), at(11, 30))

    with patch("api.services.bookings.Booking.objects.create", side_effect=db_error("08006")):
        with pytest.raises(OperationalError):
            create_booking(lesson, room, teacher)
