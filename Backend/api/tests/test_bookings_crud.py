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

from api.models import AuditLog, Booking, Notification

from .conftest import at

pytestmark = pytest.mark.django_db

UNKNOWN_ID = uuid.UUID("00000000-0000-0000-0000-000000000000")


def create_booking(client, lesson, room):
    payload = {"lesson_id": str(lesson.id), "room_id": str(room.id)}
    return client.post(reverse("booking-list-create"), payload, format="json")


def change_room(client, booking, room, **extra):
    payload = {"room_id": str(room.id), **extra}
    return client.post(reverse("booking-change-room", args=[booking.id]), payload, format="json")


@pytest.mark.req("US-03")
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


@pytest.mark.req("US-03")
def test_dispatcher_creates_booking_for_any_lesson(api_client, dispatcher, room, make_lesson):
    lesson = make_lesson(at(10), at(11, 30))
    api_client.force_authenticate(user=dispatcher)

    response = create_booking(api_client, lesson, room)

    assert response.status_code == status.HTTP_201_CREATED


@pytest.mark.req("SEC-001")
def test_teacher_cannot_book_foreign_lesson(api_client, other_teacher, room, make_lesson):
    lesson = make_lesson(at(10), at(11, 30))
    api_client.force_authenticate(user=other_teacher)

    response = create_booking(api_client, lesson, room)

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert not Booking.objects.filter(lesson=lesson).exists()


@pytest.mark.req("SEC-001")
def test_student_cannot_create_booking(api_client, student, room, make_lesson):
    lesson = make_lesson(at(10), at(11, 30))
    api_client.force_authenticate(user=student)

    response = create_booking(api_client, lesson, room)

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert not Booking.objects.filter(lesson=lesson).exists()


@pytest.mark.req("US-03")
def test_booking_with_unknown_lesson_is_rejected(api_client, teacher, room):
    api_client.force_authenticate(user=teacher)
    payload = {"lesson_id": str(UNKNOWN_ID), "room_id": str(room.id)}

    response = api_client.post(reverse("booking-list-create"), payload, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["error"]["details"][0]["field"] == "lesson_id"


@pytest.mark.req("US-03")
def test_booking_with_unknown_room_is_rejected(api_client, teacher, make_lesson):
    lesson = make_lesson(at(10), at(11, 30))
    api_client.force_authenticate(user=teacher)
    payload = {"lesson_id": str(lesson.id), "room_id": str(UNKNOWN_ID)}

    response = api_client.post(reverse("booking-list-create"), payload, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["error"]["details"][0]["field"] == "room_id"


@pytest.mark.req("US-03")
def test_overlapping_booking_in_same_room_returns_409(api_client, teacher, room, make_booking, make_lesson):
    make_booking(at(10), at(11, 30))
    overlapping_lesson = make_lesson(at(11), at(12, 30))
    api_client.force_authenticate(user=teacher)

    response = create_booking(api_client, overlapping_lesson, room)

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json()["error"]["code"] == "CONFLICT"
    assert not Booking.objects.filter(lesson=overlapping_lesson).exists()
    assert Booking.objects.filter(room=room, status=Booking.BookingStatus.ACTIVE).count() == 1


@pytest.mark.req("US-03")
def test_back_to_back_booking_in_same_room_is_allowed(api_client, teacher, room, make_booking, make_lesson):
    make_booking(at(10), at(11))
    next_lesson = make_lesson(at(11), at(12))
    api_client.force_authenticate(user=teacher)

    response = create_booking(api_client, next_lesson, room)

    assert response.status_code == status.HTTP_201_CREATED


@pytest.mark.req("US-03")
def test_second_active_booking_for_same_lesson_returns_409(api_client, teacher, room, other_room, make_lesson):
    lesson = make_lesson(at(10), at(11, 30))
    api_client.force_authenticate(user=teacher)
    create_booking(api_client, lesson, room)

    response = create_booking(api_client, lesson, other_room)

    assert response.status_code == status.HTTP_409_CONFLICT
    assert Booking.objects.filter(lesson=lesson).count() == 1


@pytest.mark.req("US-03")
def test_booking_unavailable_room_returns_409(api_client, teacher, room, make_lesson):
    room.is_available = False
    room.save()
    lesson = make_lesson(at(10), at(11, 30))
    api_client.force_authenticate(user=teacher)

    response = create_booking(api_client, lesson, room)

    assert response.status_code == status.HTTP_409_CONFLICT
    assert not Booking.objects.filter(lesson=lesson).exists()


@pytest.mark.req("US-08")
def test_teacher_retrieves_own_booking(api_client, teacher, make_booking):
    booking = make_booking(at(10), at(11, 30))
    api_client.force_authenticate(user=teacher)

    response = api_client.get(reverse("booking-detail", args=[booking.id]))

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["id"] == str(booking.id)
    assert response.json()["title"] == "Програмна інженерія"


@pytest.mark.req("US-08")
def test_teacher_cannot_retrieve_foreign_booking(api_client, other_teacher, make_booking):
    booking = make_booking(at(10), at(11, 30))
    api_client.force_authenticate(user=other_teacher)

    response = api_client.get(reverse("booking-detail", args=[booking.id]))

    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.req("US-08")
def test_retrieve_unknown_booking_returns_404(api_client, dispatcher):
    api_client.force_authenticate(user=dispatcher)

    response = api_client.get(reverse("booking-detail", args=[UNKNOWN_ID]))

    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.req("US-08", "US-04")
def test_teacher_cancels_own_booking_and_audit_record_is_written(api_client, teacher, room, make_booking):
    booking = make_booking(at(10), at(11, 30))
    api_client.force_authenticate(user=teacher)

    response = api_client.delete(reverse("booking-detail", args=[booking.id]))

    booking.refresh_from_db()
    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert booking.status == Booking.BookingStatus.CANCELLED
    record = AuditLog.objects.get(booking=booking)
    assert record.action == "cancelled"
    assert record.user == teacher
    assert record.previous_room == room


@pytest.mark.req("US-08", "US-04")
def test_cancel_twice_does_not_duplicate_audit_record(api_client, teacher, make_booking):
    booking = make_booking(at(10), at(11, 30))
    api_client.force_authenticate(user=teacher)

    api_client.delete(reverse("booking-detail", args=[booking.id]))
    response = api_client.delete(reverse("booking-detail", args=[booking.id]))

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert AuditLog.objects.filter(booking=booking).count() == 1


@pytest.mark.req("US-08")
def test_cancelled_booking_frees_the_slot(api_client, teacher, room, make_booking, make_lesson):
    booking = make_booking(at(10), at(11, 30))
    api_client.force_authenticate(user=teacher)
    api_client.delete(reverse("booking-detail", args=[booking.id]))
    new_lesson = make_lesson(at(10), at(11, 30))

    response = create_booking(api_client, new_lesson, room)

    assert response.status_code == status.HTTP_201_CREATED


@pytest.mark.req("US-08")
def test_teacher_cannot_cancel_foreign_booking(api_client, other_teacher, make_booking):
    booking = make_booking(at(10), at(11, 30))
    api_client.force_authenticate(user=other_teacher)

    response = api_client.delete(reverse("booking-detail", args=[booking.id]))

    booking.refresh_from_db()
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert booking.status == Booking.BookingStatus.ACTIVE
    assert not AuditLog.objects.filter(booking=booking).exists()


@pytest.mark.req("US-08")
def test_cancel_unknown_booking_returns_404(api_client, dispatcher):
    api_client.force_authenticate(user=dispatcher)

    response = api_client.delete(reverse("booking-detail", args=[UNKNOWN_ID]))

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.req("US-03", "US-04")
def test_teacher_changes_room_and_audit_record_is_written(api_client, teacher, room, other_room, make_booking):
    booking = make_booking(at(10), at(11, 30))
    api_client.force_authenticate(user=teacher)

    response = change_room(api_client, booking, other_room, reason="Зламався проєктор")

    booking.refresh_from_db()
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["room_id"] == str(other_room.id)
    assert booking.room == other_room
    record = AuditLog.objects.get(booking=booking)
    assert record.action == "room_changed"
    assert record.previous_room == room
    assert record.new_room == other_room
    assert record.reason == "Зламався проєктор"


@pytest.mark.req("US-03")
def test_change_room_frees_previous_room(api_client, teacher, room, other_room, make_booking, make_lesson):
    booking = make_booking(at(10), at(11, 30))
    api_client.force_authenticate(user=teacher)
    change_room(api_client, booking, other_room)
    new_lesson = make_lesson(at(10), at(11, 30))

    response = create_booking(api_client, new_lesson, room)

    assert response.status_code == status.HTTP_201_CREATED


@pytest.mark.req("US-07")
def test_change_room_notifies_group_members(api_client, teacher, student, other_room, make_booking):
    booking = make_booking(at(10), at(11, 30))
    api_client.force_authenticate(user=teacher)

    change_room(api_client, booking, other_room)

    notification = Notification.objects.get(user=student)
    assert notification.type == "room_changed"
    assert "1-226" in notification.message
    assert not notification.is_read


@pytest.mark.req("US-03")
def test_change_to_occupied_room_returns_409_and_keeps_booking(api_client, teacher, room, other_room, make_booking):
    booking = make_booking(at(10), at(11, 30))
    make_booking(at(10), at(11, 30), booking_room=other_room)
    api_client.force_authenticate(user=teacher)

    response = change_room(api_client, booking, other_room)

    booking.refresh_from_db()
    assert response.status_code == status.HTTP_409_CONFLICT
    assert booking.room == room
    assert not AuditLog.objects.filter(booking=booking).exists()


@pytest.mark.req("US-03")
def test_change_to_same_room_returns_400(api_client, teacher, room, make_booking):
    booking = make_booking(at(10), at(11, 30))
    api_client.force_authenticate(user=teacher)

    response = change_room(api_client, booking, room)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert not AuditLog.objects.filter(booking=booking).exists()


@pytest.mark.req("US-03")
def test_change_to_unknown_room_returns_400(api_client, teacher, room, make_booking):
    booking = make_booking(at(10), at(11, 30))
    api_client.force_authenticate(user=teacher)
    payload = {"room_id": str(UNKNOWN_ID)}

    response = api_client.post(reverse("booking-change-room", args=[booking.id]), payload, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["error"]["details"][0]["field"] == "room_id"


@pytest.mark.req("US-03")
def test_change_room_of_cancelled_booking_returns_409(api_client, teacher, other_room, make_booking):
    booking = make_booking(at(10), at(11, 30), status=Booking.BookingStatus.CANCELLED)
    api_client.force_authenticate(user=teacher)

    response = change_room(api_client, booking, other_room)

    assert response.status_code == status.HTTP_409_CONFLICT


@pytest.mark.req("SEC-001")
def test_student_cannot_change_room(api_client, student, other_room, make_booking, room):
    booking = make_booking(at(10), at(11, 30))
    api_client.force_authenticate(user=student)

    response = change_room(api_client, booking, other_room)

    booking.refresh_from_db()
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert booking.room == room


@pytest.mark.req("US-03")
def test_teacher_cannot_change_room_of_foreign_booking(api_client, other_teacher, other_room, make_booking, room):
    booking = make_booking(at(10), at(11, 30))
    api_client.force_authenticate(user=other_teacher)

    response = change_room(api_client, booking, other_room)

    booking.refresh_from_db()
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert booking.room == room


@pytest.mark.req("US-03")
def test_change_room_of_unknown_booking_returns_404(api_client, dispatcher, room):
    api_client.force_authenticate(user=dispatcher)
    payload = {"room_id": str(room.id)}

    response = api_client.post(reverse("booking-change-room", args=[UNKNOWN_ID]), payload, format="json")

    assert response.status_code == status.HTTP_404_NOT_FOUND
