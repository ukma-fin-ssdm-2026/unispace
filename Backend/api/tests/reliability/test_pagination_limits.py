"""
Тест надійності: граничні значення пагінації (Лаб 9, REL-H09).

Клієнт запитує список аудиторій з дуже великим лімітом (limit=100000).
Система безпечно відхиляє запит із помилкою 400 Bad Request, не допускаючи
виснаження пам'яті та перевантаження БД.

Межа перевіряється з обох боків: limit = 200 (максимум) ще приймається, а 201 і 100000 уже ні.
Те саме правило діє для GET /api/v1/users/me/bookings/.

Запуск: cd Backend && python -m pytest api/tests/reliability -v

Примітка щодо використання ШІ: тест написано з допомогою ШІ (Claude) за scavenger-hunt.md (REL-H09);
запуск `pytest` локально і в CI виконує авторка PR (Ольга Михайлик).
"""

import pytest
from django.urls import reverse
from rest_framework import status

from api.models import Room

pytestmark = [pytest.mark.django_db, pytest.mark.req("USAB-001")]

MAX_LIMIT = 200


@pytest.fixture
def rooms(db):
    return [Room.objects.create(building="1", number=f"1-{100 + n}", capacity=30) for n in range(3)]


@pytest.mark.parametrize("limit", [1, MAX_LIMIT])
def test_room_list_accepts_limit_on_the_boundary(api_client, rooms, limit):
    # Act
    response = api_client.get(reverse("room-list"), {"limit": limit})

    # Assert
    assert response.status_code == status.HTTP_200_OK
    assert len(response.json()) == min(limit, len(rooms))


@pytest.mark.parametrize("limit", [MAX_LIMIT + 1, 100000])
def test_room_list_rejects_too_large_limit_with_clear_400(api_client, rooms, limit):
    # Act
    response = api_client.get(reverse("room-list"), {"limit": limit})

    # Assert: контрольована відмова в єдиному форматі помилки, без запиту всіх рядків таблиці
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["details"][0]["field"] == "limit"


@pytest.mark.parametrize(
    "limit,expected",
    [(MAX_LIMIT, status.HTTP_200_OK), (MAX_LIMIT + 1, status.HTTP_400_BAD_REQUEST)],
)
def test_user_bookings_limit_boundary(api_client, teacher, limit, expected):
    # Arrange
    api_client.force_authenticate(user=teacher)

    # Act
    response = api_client.get(reverse("user-bookings"), {"limit": limit})

    # Assert
    assert response.status_code == expected
