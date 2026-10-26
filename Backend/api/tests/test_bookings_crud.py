"""
Тести CRUD бронювань: створення, перегляд, скасування і зміна аудиторії
(FR-011, FR-012, FR-015, FR-017, FR-020, SEC-001): TP-04, TP-06, TP-12.

Накладки перевіряє ExclusionConstraint у PostgreSQL, тому тести працюють зі справжньою базою (див. conftest.py).

Примітка щодо використання ШІ: тести написано з допомогою ШІ (Claude) за api/views.py;
запуск `pytest` локально і в CI виконує автор PR.
"""

import uuid

import pytest
from django.urls import reverse
from rest_framework import status

from api.models import Booking, Lesson, User

from .conftest import at

pytestmark = pytest.mark.django_db

UNKNOWN_ID = uuid.UUID("00000000-0000-0000-0000-000000000000")


@pytest.fixture
def make_lesson(teacher, group):
    """Фабрика: заняття без бронювання (потрібне для перевірки створення бронювання)."""

    def _make_lesson(start, end, *, lesson_teacher=None):
        return Lesson.objects.create(
            source_key=f"lesson-{uuid.uuid4()}",
            subject="Програмна інженерія",
            date=start.date(),
            start_time=start.time(),
            end_time=end.time(),
            teacher=lesson_teacher or teacher,
            group=group,
        )

    return _make_lesson


@pytest.fixture
def other_teacher(db):
    return User.objects.create(email="teacher2@ukma.edu.ua", full_name="Інший Викладач", role="teacher")


def create_booking(client, lesson, room):
    payload = {"lesson_id": str(lesson.id), "room_id": str(room.id)}
    return client.post(reverse("booking-list-create"), payload, format="json")


def test_teacher_creates_booking_for_own_lesson(api_client, teacher, room, make_lesson):
    lesson = make_lesson(at(10), at(11, 30))
    api_client.force_authenticate(user=teacher)

    response = create_booking(api_client, lesson, room)

    assert response.status_code == status.HTTP_201_CREATED
    booking = Booking.objects.get(lesson=lesson)
    assert response.json()["id"] == str(booking.id)
    assert response.json()["status"] == "active"
    assert booking.room == room
    assert booking.user == teacher
    assert booking.source == Booking.BookingSource.MANUAL


def test_dispatcher_creates_booking_for_any_lesson(api_client, dispatcher, room, make_lesson):
    lesson = make_lesson(at(10), at(11, 30))
    api_client.force_authenticate(user=dispatcher)

    response = create_booking(api_client, lesson, room)

    assert response.status_code == status.HTTP_201_CREATED


def test_teacher_cannot_book_foreign_lesson(api_client, other_teacher, room, make_lesson):
    lesson = make_lesson(at(10), at(11, 30))
    api_client.force_authenticate(user=other_teacher)

    response = create_booking(api_client, lesson, room)

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert not Booking.objects.filter(lesson=lesson).exists()


def test_student_cannot_create_booking(api_client, student, room, make_lesson):
    lesson = make_lesson(at(10), at(11, 30))
    api_client.force_authenticate(user=student)

    response = create_booking(api_client, lesson, room)

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert not Booking.objects.filter(lesson=lesson).exists()


def test_booking_with_unknown_lesson_is_rejected(api_client, teacher, room):
    api_client.force_authenticate(user=teacher)
    payload = {"lesson_id": str(UNKNOWN_ID), "room_id": str(room.id)}

    response = api_client.post(reverse("booking-list-create"), payload, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["error"]["details"][0]["field"] == "lesson_id"


def test_booking_with_unknown_room_is_rejected(api_client, teacher, make_lesson):
    lesson = make_lesson(at(10), at(11, 30))
    api_client.force_authenticate(user=teacher)
    payload = {"lesson_id": str(lesson.id), "room_id": str(UNKNOWN_ID)}

    response = api_client.post(reverse("booking-list-create"), payload, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["error"]["details"][0]["field"] == "room_id"


def test_overlapping_booking_in_same_room_returns_409(api_client, teacher, room, make_booking, make_lesson):
    make_booking(at(10), at(11, 30))
    overlapping_lesson = make_lesson(at(11), at(12, 30))
    api_client.force_authenticate(user=teacher)

    response = create_booking(api_client, overlapping_lesson, room)

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json()["error"]["code"] == "CONFLICT"
    assert not Booking.objects.filter(lesson=overlapping_lesson).exists()
    assert Booking.objects.filter(room=room, status=Booking.BookingStatus.ACTIVE).count() == 1


def test_back_to_back_booking_in_same_room_is_allowed(api_client, teacher, room, make_booking, make_lesson):
    make_booking(at(10), at(11))
    next_lesson = make_lesson(at(11), at(12))
    api_client.force_authenticate(user=teacher)

    response = create_booking(api_client, next_lesson, room)

    assert response.status_code == status.HTTP_201_CREATED


def test_second_active_booking_for_same_lesson_returns_409(api_client, teacher, room, other_room, make_lesson):
    lesson = make_lesson(at(10), at(11, 30))
    api_client.force_authenticate(user=teacher)
    create_booking(api_client, lesson, room)

    response = create_booking(api_client, lesson, other_room)

    assert response.status_code == status.HTTP_409_CONFLICT
    assert Booking.objects.filter(lesson=lesson).count() == 1


def test_booking_unavailable_room_returns_409(api_client, teacher, room, make_lesson):
    room.is_available = False
    room.save()
    lesson = make_lesson(at(10), at(11, 30))
    api_client.force_authenticate(user=teacher)

    response = create_booking(api_client, lesson, room)

    assert response.status_code == status.HTTP_409_CONFLICT
    assert not Booking.objects.filter(lesson=lesson).exists()
