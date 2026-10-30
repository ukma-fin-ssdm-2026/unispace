
"""
TP-08 / REL-001: 10 concurrent requests for the same room and time slot.

Expected: one HTTP 201, nine HTTP 409 responses.
AI usage: AI-assisted test preparation; results must be verified locally.
"""

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from django.db import connections
from django.urls import reverse
from rest_framework.test import APIClient

from api.models import Booking
from .conftest import at


@pytest.mark.req("REL-001")
def test_ten_concurrent_bookings_only_one_succeeds(
    transactional_db, teacher, room, make_lesson
):
    # Ten different lessons compete for the same room and time.
    lessons = [
        make_lesson(at(10), at(11, 30))
        for _ in range(10)
    ]

    barrier = Barrier(10)
    url = reverse("booking-list-create")

    def send_booking_request(lesson_id):
        try:
            client = APIClient()
            client.force_authenticate(user=teacher)

            # Wait until all ten workers are ready.
            barrier.wait(timeout=15)

            response = client.post(
                url,
                {
                    "lesson_id": str(lesson_id),
                    "room_id": str(room.id),
                },
                format="json",
            )

            return response.status_code

        finally:
            # Close database connections opened by this thread.
            connections.close_all()

    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(
            executor.map(
                send_booking_request,
                [lesson.id for lesson in lessons],
            )
        )

    counts = Counter(results)

    # Exactly one booking must succeed.
    assert counts[201] == 1, f"Unexpected responses: {results}"

    # The other nine requests must return a conflict.
    assert counts[409] == 9, f"Unexpected responses: {results}"

    # Only one active booking must exist in the database.
    assert Booking.objects.filter(
        room=room,
        status=Booking.BookingStatus.ACTIVE,
    ).count() == 1
