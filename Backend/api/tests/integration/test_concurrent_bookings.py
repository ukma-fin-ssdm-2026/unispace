"""
TP-08 / REL-001: Тести конкурентних запитів на бронювання та зміну аудиторії.

1. 10 одночасних запитів на бронювання однієї аудиторії на той самий слот:
   очікується один HTTP 201 та дев'ять відповідей HTTP 409.
2. 5 одночасних запитів на перенесення занять з різних аудиторій в одну вільну:
   очікується один HTTP 200 та чотири відповіді HTTP 409.

Примітка щодо використання ШІ: перший тест підготовлено за допомогою ШІ; тест конкурентної
зміни аудиторії написала, адаптувала та перевірила на реальній БД PostgreSQL Мельник Дар'я
із використанням ШІ для підготовки шаблону.
"""

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from django.db import connections
from django.urls import reverse
from rest_framework.test import APIClient

from api.models import Booking
from api.tests.conftest import at


@pytest.mark.req("REL-001")
def test_ten_concurrent_bookings_only_one_succeeds(transactional_db, teacher, room, make_lesson):
    # Десять різних занять конкурують за одну аудиторію на той самий час
    lessons = [make_lesson(at(10), at(11, 30)) for _ in range(10)]

    barrier = Barrier(10)
    url = reverse("booking-list-create")

    def send_booking_request(lesson_id):
        try:
            client = APIClient()
            client.force_authenticate(user=teacher)

            # Чекаємо, доки всі десять потоків будуть готові до одночасного запиту
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
            # Закриваємо з'єднання з БД, відкриті цим потоком
            connections.close_all()

    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(
            executor.map(
                send_booking_request,
                [lesson.id for lesson in lessons],
            )
        )

    counts = Counter(results)

    # Лише одне бронювання має завершитися успішно
    assert counts[201] == 1, f"Unexpected responses: {results}"

    # Решта дев'ять запитів мають повернути конфлікт
    assert counts[409] == 9, f"Unexpected responses: {results}"

    # У базі даних має існувати лише одне активне бронювання
    assert (
        Booking.objects.filter(
            room=room,
            status=Booking.BookingStatus.ACTIVE,
        ).count()
        == 1
    )


@pytest.mark.req("REL-001")
def test_concurrent_room_changes_to_same_target_only_one_succeeds(
    transactional_db, dispatcher, room, other_room, make_booking
):
    # П'ять активних бронювань із різних аудиторій одночасно намагаються перенестися в other_room
    bookings_list = []
    for idx in range(5):
        source_room = room if idx == 0 else type(room).objects.create(building="1", number=f"1-30{idx}", capacity=30)
        bookings_list.append(make_booking(at(10), at(11, 30), booking_room=source_room))

    barrier = Barrier(5)

    def send_change_request(booking_id):
        try:
            client = APIClient()
            client.force_authenticate(user=dispatcher)
            url = reverse("booking-change-room", args=[booking_id])

            barrier.wait(timeout=15)

            response = client.post(
                url,
                {"room_id": str(other_room.id), "reason": "Паралельне перенесення"},
                format="json",
            )
            return response.status_code
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(send_change_request, [b.id for b in bookings_list]))

    counts = Counter(results)

    assert counts[200] == 1, f"Unexpected responses: {results}"
    assert counts[409] == 4, f"Unexpected responses: {results}"
    assert (
        Booking.objects.filter(
            room=other_room,
            status=Booking.BookingStatus.ACTIVE,
        ).count()
        == 1
    )
