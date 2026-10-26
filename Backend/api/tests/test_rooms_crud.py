"""
Тести CRUD аудиторій (FR-008, FR-010, FR-018): TP-05, TP-09.

Диспетчер створює, редагує й видаляє аудиторії; перегляд відкритий усім.
Тести працюють зі справжньою базою PostgreSQL (див. conftest.py).

Примітка щодо використання ШІ: тести написано з допомогою ШІ (Claude) за api/views.py;
запуск `pytest` локально і в CI виконує автор PR.
"""

import pytest
from django.urls import reverse
from rest_framework import status

from api.models import Room

pytestmark = pytest.mark.django_db


def test_list_without_filters_returns_all_rooms(api_client, room, other_room):
    response = api_client.get(reverse("room-list"))

    assert response.status_code == status.HTTP_200_OK
    assert len(response.json()) == 2


def test_list_filters_by_projector(api_client, room, other_room):
    # room має справний проєктор, other_room - ні.
    response = api_client.get(reverse("room-list"), {"projector_working": "true"})

    assert [item["id"] for item in response.json()] == [str(room.id)]


def test_list_filters_by_capacity_and_projector_together(api_client, room, other_room):
    response = api_client.get(reverse("room-list"), {"capacity": 35, "projector_working": "true"})

    assert response.json() == []


def test_list_filters_by_building(api_client, room):
    other_building = Room.objects.create(building="7", number="7-1", capacity=10)

    response = api_client.get(reverse("room-list"), {"building": "7"})

    assert [item["id"] for item in response.json()] == [str(other_building.id)]
