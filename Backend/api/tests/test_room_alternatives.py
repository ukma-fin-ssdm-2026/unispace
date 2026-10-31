"""
Тести підбору вільних аудиторій для заміни (FR-010, US-10, US-03): TP-06, TP-09.

GET /api/v1/bookings/{id}/alternatives/ повертає аудиторії, вільні на час заняття. Згідно з FR-010 / US-10
початковий пошук обмежено бажаним корпусом; якщо там варіантів немає, відповідь містить повідомлення
з пропозицією розширити пошук (expand=true). Після розширення спершу йде бажаний корпус, далі -
найменша достатня місткість (suggest_rooms).
Зайнятість рахується за півінтервалами [start, end), як у ExclusionConstraint і intervals_overlap.

Тести написано до реалізації (специфікація для ШІ-агента); див. «Використання ШІ» в описі PR.
"""

import itertools
import uuid

import pytest
from django.urls import reverse
from rest_framework import status

from api.models import Booking, Room, User

from .conftest import at

pytestmark = [pytest.mark.django_db, pytest.mark.req("US-10")]

UNKNOWN_ID = uuid.UUID("00000000-0000-0000-0000-000000000000")
_numbers = itertools.count(300)

# ==========================================
# Фікстури та Допоміжні функції
# ==========================================


@pytest.fixture
def make_room(db):
    """Фабрика аудиторій з унікальними номерами."""

    def _make_room(*, building="1", capacity=30, is_available=True):
        return Room.objects.create(
            building=building, number=f"{building}-{next(_numbers)}", capacity=capacity, is_available=is_available
        )

    return _make_room


@pytest.fixture
def other_teacher(db):
    return User.objects.create(email="teacher2@ukma.edu.ua", full_name="Інший Викладач", role="teacher")


def get_alternatives(client, booking, **params):
    return client.get(reverse("booking-alternatives", args=[booking.id]), params)


def room_ids(response):
    return [item["id"] for item in response.json()["rooms"]]

    # ==========================================
    # Логіка доступності аудиторій (Накладки часу)
    # ==========================================


def test_room_busy_at_same_time_is_not_suggested(api_client, teacher, make_booking, make_room):
    # Arrange
    booking = make_booking(at(10), at(11, 30))
    busy = make_room()
    free = make_room()
    make_booking(at(11), at(12), booking_room=busy)
    api_client.force_authenticate(user=teacher)

    # Act
    response = get_alternatives(api_client, booking)

    # Assert
    assert response.status_code == status.HTTP_200_OK
    assert room_ids(response) == [str(free.id)]


def test_room_busy_right_before_the_lesson_is_suggested(api_client, teacher, make_booking, make_room):
    # Arrange: граничний випадок - інша пара закінчується рівно тоді, коли починається наша
    booking = make_booking(at(10), at(11, 30))
    touching = make_room()
    make_booking(at(8, 30), at(10), booking_room=touching)
    api_client.force_authenticate(user=teacher)

    # Act
    response = get_alternatives(api_client, booking)

    # Assert
    assert room_ids(response) == [str(touching.id)]


def test_room_with_cancelled_booking_is_suggested(api_client, teacher, make_booking, make_room):
    # Arrange
    booking = make_booking(at(10), at(11, 30))
    freed = make_room()
    make_booking(at(10), at(11, 30), booking_room=freed, status=Booking.BookingStatus.CANCELLED)
    api_client.force_authenticate(user=teacher)

    # Act
    response = get_alternatives(api_client, booking)

    # Assert
    assert room_ids(response) == [str(freed.id)]

    # ==========================================
    # Фільтрація та Ранжування (Місткість і Корпус)
    # ==========================================


def test_current_room_is_not_suggested(api_client, teacher, room, make_booking):
    # Arrange: інших аудиторій немає, поточна - не альтернатива
    booking = make_booking(at(10), at(11, 30))
    api_client.force_authenticate(user=teacher)

    # Act
    response = get_alternatives(api_client, booking)

    # Assert
    assert response.status_code == status.HTTP_200_OK
    assert room_ids(response) == []


def test_unavailable_and_smaller_rooms_are_not_suggested(api_client, teacher, make_booking, make_room):
    # Arrange: поточна аудиторія на 30 місць, тож за замовчуванням потрібно щонайменше 30
    booking = make_booking(at(10), at(11, 30))
    make_room(capacity=29)
    make_room(capacity=50, is_available=False)
    fits = make_room(capacity=30)
    api_client.force_authenticate(user=teacher)

    # Act
    response = get_alternatives(api_client, booking)

    # Assert
    assert room_ids(response) == [str(fits.id)]


def test_min_capacity_parameter_overrides_current_room_capacity(api_client, teacher, make_booking, make_room):
    # Arrange
    booking = make_booking(at(10), at(11, 30))
    small = make_room(capacity=20)
    api_client.force_authenticate(user=teacher)

    # Act
    response = get_alternatives(api_client, booking, min_capacity=15)

    # Assert
    assert room_ids(response) == [str(small.id)]


def test_initial_search_returns_only_rooms_of_current_building(api_client, teacher, make_booking, make_room):
    # Arrange: поточна аудиторія - корпус 1 (FR-010: початковий пошук - лише в корпусі)
    booking = make_booking(at(10), at(11, 30))
    make_room(building="4", capacity=30)
    big_same_building = make_room(building="1", capacity=60)
    snug_same_building = make_room(building="1", capacity=35)
    api_client.force_authenticate(user=teacher)

    # Act
    response = get_alternatives(api_client, booking)

    # Assert
    body = response.json()
    assert room_ids(response) == [str(snug_same_building.id), str(big_same_building.id)]
    assert body["building"] == "1"
    assert body["expanded"] is False
    assert body["message"] is None


def test_empty_building_reports_no_rooms_and_offers_expansion(api_client, teacher, make_booking, make_room):
    # Arrange: у корпусі 1 вільних аудиторій немає, у корпусі 4 є
    booking = make_booking(at(10), at(11, 30))
    make_room(building="4", capacity=30)
    api_client.force_authenticate(user=teacher)

    # Act
    response = get_alternatives(api_client, booking)

    # Assert
    body = response.json()
    assert response.status_code == status.HTTP_200_OK
    assert body["rooms"] == []
    assert body["expanded"] is False
    assert "корпусі 1" in body["message"]
    assert "expand=true" in body["message"]


def test_expanded_search_lists_preferred_building_first_then_smallest_capacity(
    api_client, teacher, make_booking, make_room
):
    # Arrange
    booking = make_booking(at(10), at(11, 30))
    other_building = make_room(building="4", capacity=30)
    big_same_building = make_room(building="1", capacity=60)
    snug_same_building = make_room(building="1", capacity=35)
    api_client.force_authenticate(user=teacher)

    # Act
    response = get_alternatives(api_client, booking, expand="true")

    # Assert
    assert response.json()["expanded"] is True
    assert room_ids(response) == [str(snug_same_building.id), str(big_same_building.id), str(other_building.id)]


def test_expanded_search_without_any_rooms_reports_it(api_client, teacher, make_booking):
    # Arrange: крім поточної, аудиторій немає взагалі
    booking = make_booking(at(10), at(11, 30))
    api_client.force_authenticate(user=teacher)

    # Act
    body = get_alternatives(api_client, booking, expand="true").json()

    # Assert
    assert body["rooms"] == []
    assert "жодному корпусі" in body["message"]


def test_building_parameter_changes_searched_building(api_client, teacher, make_booking, make_room):
    # Arrange
    booking = make_booking(at(10), at(11, 30))
    same_building = make_room(building="1", capacity=30)
    requested_building = make_room(building="4", capacity=30)
    api_client.force_authenticate(user=teacher)

    # Act
    initial = get_alternatives(api_client, booking, building="4")
    expanded = get_alternatives(api_client, booking, building="4", expand="true")

    # Assert
    assert initial.json()["building"] == "4"
    assert room_ids(initial) == [str(requested_building.id)]
    assert room_ids(expanded) == [str(requested_building.id), str(same_building.id)]

    # ==========================================
    # Контракт API та Обробка помилок
    # ==========================================


def test_response_contains_room_details(api_client, teacher, make_booking, make_room):
    # Arrange
    booking = make_booking(at(10), at(11, 30))
    make_room(building="2", capacity=45)
    api_client.force_authenticate(user=teacher)

    # Act
    item = get_alternatives(api_client, booking, expand="true").json()["rooms"][0]

    # Assert
    assert item["building"] == "2"
    assert item["capacity"] == 45
    assert {"number", "projector_working", "has_computers"} <= item.keys()


@pytest.mark.parametrize("min_capacity", [0, -1, "abc"])
def test_invalid_min_capacity_returns_400(api_client, teacher, make_booking, min_capacity):
    # Arrange
    booking = make_booking(at(10), at(11, 30))
    api_client.force_authenticate(user=teacher)

    # Act
    response = get_alternatives(api_client, booking, min_capacity=min_capacity)

    # Assert
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["error"]["details"][0]["field"] == "min_capacity"


def test_invalid_expand_returns_400(api_client, teacher, make_booking):
    # Arrange
    booking = make_booking(at(10), at(11, 30))
    api_client.force_authenticate(user=teacher)

    # Act
    response = get_alternatives(api_client, booking, expand="maybe")

    # Assert
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["error"]["details"][0]["field"] == "expand"


def test_cancelled_booking_returns_409(api_client, teacher, make_booking):
    # Arrange
    booking = make_booking(at(10), at(11, 30), status=Booking.BookingStatus.CANCELLED)
    api_client.force_authenticate(user=teacher)

    # Act
    response = get_alternatives(api_client, booking)

    # Assert
    assert response.status_code == status.HTTP_409_CONFLICT


def test_unknown_booking_returns_404(api_client, dispatcher):
    # Arrange
    api_client.force_authenticate(user=dispatcher)

    # Act
    response = api_client.get(reverse("booking-alternatives", args=[UNKNOWN_ID]))

    # Assert
    assert response.status_code == status.HTTP_404_NOT_FOUND

    # ==========================================
    # Права доступу (Permissions)
    # ==========================================


def test_dispatcher_sees_alternatives_for_any_booking(api_client, dispatcher, make_booking, make_room):
    # Arrange
    booking = make_booking(at(10), at(11, 30))
    free = make_room()
    api_client.force_authenticate(user=dispatcher)

    # Act
    response = get_alternatives(api_client, booking)

    # Assert
    assert room_ids(response) == [str(free.id)]


def test_teacher_cannot_see_alternatives_for_foreign_booking(api_client, other_teacher, make_booking):
    # Arrange
    booking = make_booking(at(10), at(11, 30))
    api_client.force_authenticate(user=other_teacher)

    # Act
    response = get_alternatives(api_client, booking)

    # Assert
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.parametrize("role", ["student", None])
def test_student_and_anonymous_cannot_see_alternatives(api_client, student, make_booking, role):
    # Arrange
    booking = make_booking(at(10), at(11, 30))
    if role == "student":
        api_client.force_authenticate(user=student)

    # Act
    response = get_alternatives(api_client, booking)

    # Assert
    assert response.status_code == status.HTTP_403_FORBIDDEN
