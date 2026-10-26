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


@pytest.fixture
def room_payload():
    return {"building": "2", "number": "2-101", "capacity": 50, "projector_working": True}


def test_dispatcher_creates_room_and_gets_201(api_client, dispatcher, room_payload):
    api_client.force_authenticate(user=dispatcher)

    response = api_client.post(reverse("room-list"), room_payload, format="json")

    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["number"] == "2-101"
    assert Room.objects.filter(building="2", number="2-101", capacity=50).exists()


def test_teacher_cannot_create_room(api_client, teacher, room_payload):
    api_client.force_authenticate(user=teacher)

    response = api_client.post(reverse("room-list"), room_payload, format="json")

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert not Room.objects.filter(number="2-101").exists()


def test_anonymous_cannot_create_room(api_client, room_payload):
    response = api_client.post(reverse("room-list"), room_payload, format="json")

    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_room_with_zero_capacity_is_rejected(api_client, dispatcher, room_payload):
    api_client.force_authenticate(user=dispatcher)
    room_payload["capacity"] = 0

    response = api_client.post(reverse("room-list"), room_payload, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert not Room.objects.filter(number="2-101").exists()


def test_duplicate_room_number_in_building_is_rejected(api_client, dispatcher, room):
    api_client.force_authenticate(user=dispatcher)
    payload = {"building": room.building, "number": room.number, "capacity": 20}

    response = api_client.post(reverse("room-list"), payload, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert Room.objects.filter(building=room.building, number=room.number).count() == 1


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
