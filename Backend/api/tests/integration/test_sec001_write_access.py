"""
Вимірюваний тест SEC-001 (TP-12): усі write-ендпоінти бронювань закриті для студента й аноніма.

Поріг: 100% спроб запису (3 ендпоінти x 2 ролі = 6 спроб) отримують HTTP 403,
у базі не змінюється жодного бронювання, запису аудиту чи сповіщення (0 змін).

Запуск: cd Backend && python -m pytest api/tests/test_sec001_write_access.py -v

Примітка щодо використання ШІ: тест написано з допомогою ШІ (Claude) за SEC-001 з requirements.md
і маршрутами api/urls.py; запуск `pytest` локально і в CI виконує авторка PR (Ольга Михайлик).
"""

import pytest
from django.urls import reverse
from rest_framework import status

from api.models import AuditLog, Booking, Notification

from api.tests.conftest import at

pytestmark = [pytest.mark.django_db, pytest.mark.req("SEC-001")]

WRITE_ACTIONS = ["create", "cancel", "change_room"]
ROLES = ["anonymous", "student"]


def _send(client, action, booking, lesson, other_room):
    if action == "create":
        payload = {"lesson_id": str(lesson.id), "room_id": str(other_room.id)}
        return client.post(reverse("booking-list-create"), payload, format="json")
    if action == "cancel":
        return client.delete(reverse("booking-detail", args=[booking.id]))
    payload = {"room_id": str(other_room.id), "reason": "SEC-001"}
    return client.post(reverse("booking-change-room", args=[booking.id]), payload, format="json")


def _snapshot():
    """Стан, який не має змінитися: усі бронювання (аудиторія, статус) і кількість записів аудиту та сповіщень."""
    bookings = sorted(Booking.objects.values_list("id", "room_id", "status"))
    return bookings, AuditLog.objects.count(), Notification.objects.count()


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("action", WRITE_ACTIONS)
def test_write_endpoint_is_forbidden_and_changes_nothing(
    api_client, student, other_room, make_booking, make_lesson, role, action
):
    # Arrange: наявне бронювання й заняття без бронювання
    booking = make_booking(at(10), at(11, 30))
    free_lesson = make_lesson(at(12), at(13, 30))
    if role == "student":
        api_client.force_authenticate(user=student)
    before = _snapshot()

    # Act
    response = _send(api_client, action, booking, free_lesson, other_room)

    # Assert: 403 і жодної зміни в базі
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert _snapshot() == before
