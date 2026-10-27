"""
Тести CRUD аудиторій (FR-008, FR-010, FR-018): TP-05, TP-09.

Диспетчер створює, редагує й видаляє аудиторії; перегляд відкритий усім.
Тести працюють зі справжньою базою PostgreSQL (див. conftest.py).

Примітка щодо використання ШІ: тести написано з допомогою ШІ (Claude) за api/views.py;
запуск `pytest` локально і в CI виконує автор PR.
"""

import uuid
import pytest
from django.urls import reverse
from rest_framework import status

from api.models import Room
from .conftest import at

pytestmark = pytest.mark.django_db
UNKNOWN_ID = uuid.UUID("00000000-0000-0000-0000-000000000000")


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


def test_anyone_can_retrieve_room(api_client, room):
    response = api_client.get(reverse("room-detail", args=[room.id]))

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["id"] == str(room.id)
    assert response.json()["capacity"] == room.capacity


def test_retrieve_unknown_room_returns_404(api_client):
    response = api_client.get(reverse("room-detail", args=[UNKNOWN_ID]))

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_dispatcher_updates_room_partially(api_client, dispatcher, room):
    api_client.force_authenticate(user=dispatcher)

    response = api_client.patch(reverse("room-detail", args=[room.id]), {"capacity": 45}, format="json")

    room.refresh_from_db()
    assert response.status_code == status.HTTP_200_OK
    assert room.capacity == 45
    assert room.number == "1-225"


def test_teacher_cannot_update_room(api_client, teacher, room):
    api_client.force_authenticate(user=teacher)

    response = api_client.patch(reverse("room-detail", args=[room.id]), {"capacity": 45}, format="json")

    room.refresh_from_db()
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert room.capacity == 30


def test_update_unknown_room_returns_404(api_client, dispatcher):
    api_client.force_authenticate(user=dispatcher)

    response = api_client.patch(reverse("room-detail", args=[UNKNOWN_ID]), {"capacity": 45}, format="json")

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_update_with_invalid_capacity_returns_400(api_client, dispatcher, room):
    api_client.force_authenticate(user=dispatcher)

    response = api_client.patch(reverse("room-detail", args=[room.id]), {"capacity": -5}, format="json")

    room.refresh_from_db()
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert room.capacity == 30


def test_dispatcher_deletes_unused_room(api_client, dispatcher, room):
    api_client.force_authenticate(user=dispatcher)

    response = api_client.delete(reverse("room-detail", args=[room.id]))

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert not Room.objects.filter(id=room.id).exists()


def test_room_with_bookings_cannot_be_deleted(api_client, dispatcher, room, make_booking):
    make_booking(at(10), at(11, 30))
    api_client.force_authenticate(user=dispatcher)

    response = api_client.delete(reverse("room-detail", args=[room.id]))

    assert response.status_code == status.HTTP_409_CONFLICT
    assert Room.objects.filter(id=room.id).exists()


def test_teacher_cannot_delete_room(api_client, teacher, room):
    api_client.force_authenticate(user=teacher)

    response = api_client.delete(reverse("room-detail", args=[room.id]))

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert Room.objects.filter(id=room.id).exists()


def test_delete_unknown_room_returns_404(api_client, dispatcher):
    api_client.force_authenticate(user=dispatcher)

    response = api_client.delete(reverse("room-detail", args=[UNKNOWN_ID]))

    assert response.status_code == status.HTTP_404_NOT_FOUND
