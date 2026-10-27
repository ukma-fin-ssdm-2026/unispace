"""
Спільні фікстури pytest для тестів бізнес-логіки (Lab06).

Фікстури створюють мінімальний валідний набір даних: групу, викладача, аудиторію
і фабрику бронювань. Кожне бронювання отримує власне заняття, бо модель дозволяє
лише одне активне бронювання на заняття (uniq_active_booking_per_lesson).

Тести, які використовують ці фікстури, працюють зі справжньою базою PostgreSQL
(позначка @pytest.mark.django_db), бо правило накладок бронювань (ExclusionConstraint)
існує лише в PostgreSQL. Локально: docker compose up -d; у CI - сервіс postgres.

Примітка щодо використання ШІ: фікстури написано з допомогою ШІ (Claude) за моделями
api/models.py; перевірено запуском pytest локально і в CI.
"""

import itertools
from datetime import date, datetime, time, timezone

import pytest

from api.models import AcademicGroup, AuditLog, Booking, Lesson, Room, User
from rest_framework.test import APIClient

_counter = itertools.count(1)


@pytest.fixture
def group(db):
    return AcademicGroup.objects.create(name="ІПЗ-3", source_key="group-ipz-3")


@pytest.fixture
def teacher(db):
    # User.objects.create, а не create_user: у моделі User ще немає власного менеджера для входу через email.
    return User.objects.create(email="teacher@ukma.edu.ua", full_name="Тестовий Викладач", role="teacher")


@pytest.fixture
def student(db, group):
    return User.objects.create(email="student@ukma.edu.ua", full_name="Тестовий Студент", role="student", group=group)


@pytest.fixture
def dispatcher(db):
    return User.objects.create(email="dispatcher@ukma.edu.ua", full_name="Тестовий Диспетчер", role="dispatcher")


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def room(db):
    return Room.objects.create(building="1", number="1-225", capacity=30, projector_working=True)


@pytest.fixture
def make_booking(teacher, group, room):
    """Фабрика: створює бронювання (і окреме заняття для нього) на заданий час."""

    def _make_booking(start, end, *, booking_room=None, status=Booking.BookingStatus.ACTIVE):
        n = next(_counter)
        lesson = Lesson.objects.create(
            source_key=f"lesson-{n}",
            subject="Програмна інженерія",
            date=start.date(),
            start_time=start.time(),
            end_time=end.time(),
            teacher=teacher,
            group=group,
        )
        return Booking.objects.create(
            lesson=lesson,
            room=booking_room or room,
            status=status,
        )

    return _make_booking


@pytest.fixture
def other_room(db):
    return Room.objects.create(building="1", number="1-226", capacity=40)


@pytest.fixture
def audit_log(make_booking, teacher, room, other_room):
    """Збережений запис аудиту: викладач переніс заняття з room в other_room."""
    booking = make_booking(at(10), at(11, 30))
    return AuditLog.objects.create(
        booking=booking,
        user=teacher,
        action="room_changed",
        previous_room=room,
        new_room=other_room,
        reason="Зламався проєктор",
    )


def at(hour, minute=0, day=date(2026, 10, 20)):
    """Зручний конструктор часу в UTC для тестів: at(10, 30) -> 2026-10-20 10:30 UTC."""
    return datetime.combine(day, time(hour, minute), tzinfo=timezone.utc)
