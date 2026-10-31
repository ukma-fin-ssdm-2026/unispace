"""
Тести перегляду аудит-логу диспетчером (FR-017, US-04): GET /api/v1/audit-logs/.

Запис в журнал створюють перенесення й скасування бронювань (test_bookings_crud.py), незмінність
записів перевіряє test_audit_log.py. Тут перевіряємо читання: доступ лише для диспетчера, поля запису,
порядок, фільтри, пагінацію й відсутність змін через API. Тести працюють зі справжньою базою PostgreSQL.

Примітка щодо використання ШІ: тести й ендпоінт написано з допомогою ШІ (Claude) за FR-017 і US-04;
запуск `pytest` локально і в CI виконує автор PR.
"""

from datetime import date
from unittest.mock import patch
from uuid import uuid4

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from api.models import AuditLog, Room

from .conftest import at

pytestmark = [pytest.mark.django_db, pytest.mark.req("US-04")]

# ==========================================
# Хелпери
# ==========================================


def get_logs(client, **params):
    return client.get(reverse("audit-log-list"), params)


def log_at(when, booking, user, action="room_changed", previous_room=None, new_room=None, reason=""):
    """Запис аудиту із заданим часом: created_at проставляється автоматично, тому підміняємо поточний час."""
    with patch("django.utils.timezone.now", return_value=when):
        return AuditLog.objects.create(
            booking=booking,
            user=user,
            action=action,
            previous_room=previous_room,
            new_room=new_room,
            reason=reason,
        )


@pytest.fixture
def dispatcher_client(api_client, dispatcher):
    api_client.force_authenticate(user=dispatcher)
    return api_client


# ==========================================
# Доступ (лише диспетчер)
# ==========================================


def test_anonymous_cannot_view_audit_log(api_client):
    response = get_logs(api_client)

    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_student_cannot_view_audit_log(api_client, student):
    api_client.force_authenticate(user=student)

    response = get_logs(api_client)

    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_teacher_cannot_view_audit_log(api_client, teacher):
    api_client.force_authenticate(user=teacher)

    response = get_logs(api_client)

    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_dispatcher_gets_empty_list_when_nothing_is_logged(dispatcher_client):
    response = get_logs(dispatcher_client)

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == []


# ==========================================
# Вміст запису
# ==========================================


def test_entry_contains_who_when_what_and_why(dispatcher_client, audit_log, teacher, room, other_room):
    response = get_logs(dispatcher_client)

    assert response.status_code == status.HTTP_200_OK
    [entry] = response.json()
    assert entry["id"] == str(audit_log.id)
    assert entry["booking_id"] == str(audit_log.booking_id)
    assert entry["subject"] == "Програмна інженерія"
    assert entry["action"] == "room_changed"
    assert entry["user"] == {"id": str(teacher.id), "email": teacher.email, "full_name": teacher.full_name}
    assert entry["previous_room"] == {"id": str(room.id), "building": room.building, "number": room.number}
    assert entry["new_room"] == {"id": str(other_room.id), "building": other_room.building, "number": other_room.number}
    assert entry["reason"] == "Зламався проєктор"
    assert entry["created_at"]


def test_cancellation_entry_has_previous_room_and_no_new_room(dispatcher_client, make_booking, teacher, room):
    booking = make_booking(at(10), at(11, 30))
    log_at(at(9), booking, teacher, action="cancelled", previous_room=room)

    [entry] = get_logs(dispatcher_client).json()

    assert entry["action"] == "cancelled"
    assert entry["previous_room"]["id"] == str(room.id)
    assert entry["new_room"] is None


def test_room_change_made_through_api_is_visible_to_dispatcher(
    dispatcher_client, make_booking, teacher, room, other_room
):
    # Arrange: викладач переносить власне заняття через API
    booking = make_booking(at(10), at(11, 30))
    teacher_client = APIClient()
    teacher_client.force_authenticate(user=teacher)

    # Act
    change = teacher_client.post(
        reverse("booking-change-room", args=[booking.id]),
        {"room_id": str(other_room.id), "reason": "Ремонт у кабінеті"},
        format="json",
    )
    response = get_logs(dispatcher_client, booking_id=str(booking.id))

    # Assert
    assert change.status_code == status.HTTP_200_OK
    [entry] = response.json()
    assert entry["action"] == "room_changed"
    assert entry["user"]["id"] == str(teacher.id)
    assert entry["previous_room"]["id"] == str(room.id)
    assert entry["new_room"]["id"] == str(other_room.id)
    assert entry["reason"] == "Ремонт у кабінеті"


# ==========================================
# Порядок і пагінація
# ==========================================


def test_entries_are_sorted_newest_first(dispatcher_client, make_booking, teacher, room, other_room):
    booking = make_booking(at(10), at(11, 30))
    old = log_at(at(8, day=date(2026, 10, 18)), booking, teacher, previous_room=room, new_room=other_room)
    new = log_at(at(8, day=date(2026, 10, 19)), booking, teacher, previous_room=other_room, new_room=room)

    ids = [entry["id"] for entry in get_logs(dispatcher_client).json()]

    assert ids == [str(new.id), str(old.id)]


def test_limit_and_offset_page_through_entries(dispatcher_client, make_booking, teacher, room):
    booking = make_booking(at(10), at(11, 30))
    logs = [
        log_at(at(8, day=date(2026, 10, day)), booking, teacher, action="cancelled", previous_room=room)
        for day in (10, 11, 12)
    ]
    newest_first = [str(log.id) for log in reversed(logs)]

    first_page = get_logs(dispatcher_client, limit=2).json()
    second_page = get_logs(dispatcher_client, limit=2, offset=2).json()

    assert [entry["id"] for entry in first_page] == newest_first[:2]
    assert [entry["id"] for entry in second_page] == newest_first[2:]


def test_listing_uses_constant_number_of_queries(
    dispatcher_client, make_booking, teacher, room, other_room, django_assert_max_num_queries
):
    for hour in (8, 9, 10, 11):
        log_at(at(hour), make_booking(at(12), at(13)), teacher, previous_room=room, new_room=other_room)

    with django_assert_max_num_queries(3):
        response = get_logs(dispatcher_client)

    assert len(response.json()) == 4


# ==========================================
# Фільтри
# ==========================================


def test_filter_by_booking_returns_only_its_entries(dispatcher_client, make_booking, teacher, room):
    first = make_booking(at(10), at(11, 30))
    second = make_booking(at(12), at(13, 30))
    wanted = log_at(at(8), first, teacher, action="cancelled", previous_room=room)
    log_at(at(9), second, teacher, action="cancelled", previous_room=room)

    response = get_logs(dispatcher_client, booking_id=str(first.id))

    assert [entry["id"] for entry in response.json()] == [str(wanted.id)]


def test_filter_by_unknown_booking_returns_empty_list(dispatcher_client, audit_log):
    response = get_logs(dispatcher_client, booking_id=str(uuid4()))

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == []


def test_filter_by_room_matches_previous_and_new_room(dispatcher_client, make_booking, teacher, room, other_room):
    third_room = Room.objects.create(building="2", number="2-101", capacity=20)
    booking = make_booking(at(10), at(11, 30))
    moved_out = log_at(at(8), booking, teacher, previous_room=room, new_room=other_room)
    moved_in = log_at(at(9), booking, teacher, previous_room=third_room, new_room=room)
    log_at(at(10), booking, teacher, previous_room=third_room, new_room=other_room)

    response = get_logs(dispatcher_client, room_id=str(room.id))

    assert {entry["id"] for entry in response.json()} == {str(moved_out.id), str(moved_in.id)}


def test_filter_by_action(dispatcher_client, make_booking, teacher, room, other_room):
    booking = make_booking(at(10), at(11, 30))
    log_at(at(8), booking, teacher, action="room_changed", previous_room=room, new_room=other_room)
    cancelled = log_at(at(9), booking, teacher, action="cancelled", previous_room=other_room)

    response = get_logs(dispatcher_client, action="cancelled")

    assert [entry["id"] for entry in response.json()] == [str(cancelled.id)]


def test_filter_by_date_range_is_inclusive(dispatcher_client, make_booking, teacher, room):
    booking = make_booking(at(10), at(11, 30))
    log_at(at(10, day=date(2026, 10, 9)), booking, teacher, action="cancelled", previous_room=room)
    start = log_at(at(10, day=date(2026, 10, 10)), booking, teacher, action="cancelled", previous_room=room)
    end = log_at(at(10, day=date(2026, 10, 12)), booking, teacher, action="cancelled", previous_room=room)
    log_at(at(10, day=date(2026, 10, 13)), booking, teacher, action="cancelled", previous_room=room)

    response = get_logs(dispatcher_client, date_from="2026-10-10", date_to="2026-10-12")

    assert {entry["id"] for entry in response.json()} == {str(start.id), str(end.id)}


# ==========================================
# Невалідні параметри (USAB-001: 400, а не 500)
# ==========================================


@pytest.mark.parametrize(
    "params, field",
    [
        ({"limit": 0}, "limit"),
        ({"limit": 201}, "limit"),
        ({"offset": -1}, "offset"),
        ({"booking_id": "not-a-uuid"}, "booking_id"),
        ({"room_id": "not-a-uuid"}, "room_id"),
        ({"action": "deleted"}, "action"),
        ({"date_from": "yesterday"}, "date_from"),
        ({"date_from": "2026-10-12", "date_to": "2026-10-10"}, "non_field_errors"),
    ],
)
def test_invalid_query_returns_400_with_standard_error(dispatcher_client, params, field):
    response = get_logs(dispatcher_client, **params)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert field in {detail["field"] for detail in error["details"]}


# ==========================================
# Лише читання (незмінність через API)
# ==========================================


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_audit_log_cannot_be_modified_through_api(dispatcher_client, audit_log, method):
    url = reverse("audit-log-list")

    response = getattr(dispatcher_client, method)(url, {}, format="json")

    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
    audit_log.refresh_from_db()
    assert audit_log.reason == "Зламався проєктор"
