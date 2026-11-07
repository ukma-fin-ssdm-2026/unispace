import pytest

from api.services.available_slots import find_free_slots
from datetime import datetime
from django.urls import reverse
from django.utils import timezone


@pytest.mark.req("USAB-001")
def test_no_bookings_returns_full_day():
    result = find_free_slots([], "08:00", "20:00")

    assert result == ["08:00-20:00"]


@pytest.mark.req("USAB-001")
def test_bookings_split_free_time():
    bookings = [
        ("10:00", "11:30"),
        ("14:00", "15:30"),
    ]

    result = find_free_slots(bookings, "08:00", "20:00")

    assert result == [
        "08:00-10:00",
        "11:30-14:00",
        "15:30-20:00",
    ]


@pytest.mark.req("USAB-001")
def test_adjacent_bookings():
    bookings = [
        ("10:00", "11:00"),
        ("11:00", "12:00"),
    ]

    result = find_free_slots(bookings, "08:00", "20:00")

    assert result == ["08:00-10:00", "12:00-20:00"]


@pytest.mark.req("USAB-001")
def test_full_day_booked():
    result = find_free_slots([("08:00", "20:00")], "08:00", "20:00")

    assert result == []


@pytest.mark.req("USAB-001")
def test_unsorted_bookings():
    bookings = [
        ("14:00", "15:00"),
        ("09:00", "10:00"),
    ]

    result = find_free_slots(bookings, "08:00", "20:00")

    assert result == [
        "08:00-09:00",
        "10:00-14:00",
        "15:00-20:00",
    ]


@pytest.mark.django_db
@pytest.mark.req("USAB-001")
def test_active_booking_blocks_time(api_client, room, make_booking):
    start = timezone.make_aware(datetime(2026, 10, 28, 10, 0))
    end = timezone.make_aware(datetime(2026, 10, 28, 11, 30))

    make_booking(start, end)

    response = api_client.get(
        reverse("available-slots"),
        {"room_id": str(room.id), "date": "2026-10-28"},
    )

    assert response.status_code == 200
    assert response.json()["available_slots"] == [
        "08:00-10:00",
        "11:30-20:00",
    ]


@pytest.mark.django_db
@pytest.mark.req("USAB-001")
def test_cancelled_booking_does_not_block_time(api_client, room, make_booking):
    start = timezone.make_aware(datetime(2026, 10, 28, 10, 0))
    end = timezone.make_aware(datetime(2026, 10, 28, 11, 30))

    make_booking(start, end, status="cancelled")

    response = api_client.get(
        reverse("available-slots"),
        {"room_id": str(room.id), "date": "2026-10-28"},
    )

    assert response.status_code == 200
    assert response.json()["available_slots"] == ["08:00-20:00"]


@pytest.mark.django_db
@pytest.mark.req("USAB-001")
def test_other_room_booking_does_not_block_time(api_client, room, other_room, make_booking):
    start = timezone.make_aware(datetime(2026, 10, 28, 10, 0))
    end = timezone.make_aware(datetime(2026, 10, 28, 11, 30))

    make_booking(start, end, booking_room=other_room)

    response = api_client.get(
        reverse("available-slots"),
        {"room_id": str(room.id), "date": "2026-10-28"},
    )

    assert response.status_code == 200
    assert response.json()["available_slots"] == ["08:00-20:00"]


@pytest.mark.django_db
@pytest.mark.req("USAB-001")
def test_other_day_booking_does_not_block_time(api_client, room, make_booking):
    start = timezone.make_aware(datetime(2026, 10, 27, 10, 0))
    end = timezone.make_aware(datetime(2026, 10, 27, 11, 30))

    make_booking(start, end)

    response = api_client.get(
        reverse("available-slots"),
        {"room_id": str(room.id), "date": "2026-10-28"},
    )

    assert response.status_code == 200
    assert response.json()["available_slots"] == ["08:00-20:00"]


@pytest.mark.django_db
@pytest.mark.req("USAB-001")
def test_booking_until_end_of_day(api_client, room, make_booking):
    start = timezone.make_aware(datetime(2026, 10, 28, 18, 0))
    end = timezone.make_aware(datetime(2026, 10, 28, 20, 0))

    make_booking(start, end)

    response = api_client.get(
        reverse("available-slots"),
        {
            "room_id": str(room.id),
            "date": "2026-10-28",
        },
    )

    assert response.status_code == 200
    assert response.json()["available_slots"] == ["08:00-18:00"]


@pytest.mark.parametrize(
    "bookings, expected",
    [
        # Booking starts before working hours
        (
            [("07:00", "09:00")],
            ["09:00-20:00"],
        ),
        # Booking ends after working hours
        (
            [("19:00", "21:00")],
            ["08:00-19:00"],
        ),
        # Bookings completely outside working hours
        (
            [("06:00", "07:00"), ("21:00", "22:00")],
            ["08:00-20:00"],
        ),
        # Overlapping bookings should not create false free slots
        (
            [("10:00", "12:00"), ("11:00", "13:00")],
            ["08:00-10:00", "13:00-20:00"],
        ),
        # Booking covers the entire working day
        (
            [("07:00", "21:00")],
            [],
        ),
        # Nested bookings should not move the end time backwards
        (
            [("10:00", "15:00"), ("11:00", "12:00")],
            ["08:00-10:00", "15:00-20:00"],
        ),
    ],
)
@pytest.mark.req("USAB-001")
def test_find_free_slots_boundary_and_overlap_cases(bookings, expected):
    result = find_free_slots(bookings, "08:00", "20:00")

    assert result == expected
