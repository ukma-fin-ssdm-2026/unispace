"""
Тести блоку «Попередня пара» (FR-019, US-02): GET /api/v1/bookings/{id}/previous/.

Викладач бачить дисципліну, групу й ПІБ викладача попереднього заняття в тій самій аудиторії того ж дня;
якщо попередньої пари не було, відповідь містить повідомлення «Попередньої пари не було» (без висновків
про ключі). Сама функція пошуку покрита в test_room_occupancy.py. Тести працюють зі справжньою базою PostgreSQL.

Примітка щодо використання ШІ: тести й ендпоінт написано з допомогою ШІ (Claude) за FR-019 і US-02;
запуск `pytest` локально і в CI виконує автор PR.
"""

import uuid
from datetime import date

import pytest
from django.urls import reverse
from rest_framework import status

from api.models import AcademicGroup, Booking, Lesson

from .conftest import at

pytestmark = [pytest.mark.django_db, pytest.mark.req("US-02")]

NO_PREVIOUS_MESSAGE = "Попередньої пари не було"

# ==========================================
# Фікстури та Хелпери
# ==========================================


@pytest.fixture
def previous_group(db):
    return AcademicGroup.objects.create(name="ІПЗ-4", source_key="group-ipz-4")


@pytest.fixture
def book_previous(other_teacher, previous_group):
    """Фабрика: бронювання заняття іншого викладача й іншої групи в заданій аудиторії."""

    def _book(start, end, *, in_room, status=Booking.BookingStatus.ACTIVE):
        lesson = Lesson.objects.create(
            source_key=f"previous-{uuid.uuid4()}",
            subject="Бази даних",
            date=start.date(),
            start_time=start.time(),
            end_time=end.time(),
            teacher=other_teacher,
            group=previous_group,
        )
        return Booking.objects.create(lesson=lesson, room=in_room, status=status)

    return _book


def get_previous(client, booking):
    return client.get(reverse("booking-previous", args=[booking.id]))


# ==========================================
# Є попередня пара
# ==========================================


def test_teacher_sees_subject_group_and_teacher_of_previous_lesson(
    api_client, teacher, make_booking, book_previous, room
):
    book_previous(at(8, 30), at(10, 5), in_room=room)
    current = make_booking(at(10, 25), at(12))
    api_client.force_authenticate(user=teacher)

    response = get_previous(api_client, current)

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["message"] is None
    previous = body["previous_lesson"]
    assert previous["subject"] == "Бази даних"
    assert previous["group"] == "ІПЗ-4"
    assert previous["teacher"] == "Інший Викладач"
    assert previous["start_time"]
    assert previous["end_time"]


def test_back_to_back_lesson_is_previous(api_client, teacher, make_booking, book_previous, room):
    book_previous(at(8, 30), at(10), in_room=room)
    current = make_booking(at(10), at(11, 30))
    api_client.force_authenticate(user=teacher)

    body = get_previous(api_client, current).json()

    assert body["previous_lesson"]["subject"] == "Бази даних"


def test_latest_of_several_earlier_lessons_is_returned(api_client, teacher, make_booking, book_previous, room):
    make_booking(at(8, 30), at(10, 5))
    book_previous(at(10, 25), at(12), in_room=room)
    current = make_booking(at(12, 20), at(13, 55))
    api_client.force_authenticate(user=teacher)

    previous = get_previous(api_client, current).json()["previous_lesson"]

    assert previous["subject"] == "Бази даних"
    assert previous["teacher"] == "Інший Викладач"


# ==========================================
# Попередньої пари не було
# ==========================================


def test_first_lesson_of_the_day_has_no_previous_lesson(api_client, teacher, make_booking):
    current = make_booking(at(8, 30), at(10, 5))
    api_client.force_authenticate(user=teacher)

    response = get_previous(api_client, current)

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"previous_lesson": None, "message": NO_PREVIOUS_MESSAGE}


def test_message_makes_no_claims_about_keys(api_client, teacher, make_booking):
    current = make_booking(at(8, 30), at(10, 5))
    api_client.force_authenticate(user=teacher)

    message = get_previous(api_client, current).json()["message"]

    assert "ключ" not in message.lower()


def test_cancelled_previous_booking_is_ignored(api_client, teacher, make_booking, book_previous, room):
    book_previous(at(8, 30), at(10, 5), in_room=room, status=Booking.BookingStatus.CANCELLED)
    current = make_booking(at(10, 25), at(12))
    api_client.force_authenticate(user=teacher)

    body = get_previous(api_client, current).json()

    assert body["previous_lesson"] is None
    assert body["message"] == NO_PREVIOUS_MESSAGE


def test_lesson_in_another_room_is_ignored(api_client, teacher, make_booking, book_previous, other_room):
    book_previous(at(8, 30), at(10, 5), in_room=other_room)
    current = make_booking(at(10, 25), at(12))
    api_client.force_authenticate(user=teacher)

    assert get_previous(api_client, current).json()["previous_lesson"] is None


def test_lesson_on_another_day_is_ignored(api_client, teacher, make_booking, book_previous, room):
    book_previous(at(18, 0, day=date(2026, 10, 19)), at(19, 35, day=date(2026, 10, 19)), in_room=room)
    current = make_booking(at(8, 30), at(10, 5))
    api_client.force_authenticate(user=teacher)

    assert get_previous(api_client, current).json()["previous_lesson"] is None


# ==========================================
# Права доступу й помилки
# ==========================================


def test_dispatcher_can_view_previous_lesson_of_any_booking(api_client, dispatcher, make_booking, book_previous, room):
    book_previous(at(8, 30), at(10, 5), in_room=room)
    current = make_booking(at(10, 25), at(12))
    api_client.force_authenticate(user=dispatcher)

    response = get_previous(api_client, current)

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["previous_lesson"]["subject"] == "Бази даних"


def test_teacher_cannot_view_previous_lesson_of_foreign_booking(api_client, other_teacher, make_booking):
    current = make_booking(at(10, 25), at(12))
    api_client.force_authenticate(user=other_teacher)

    response = get_previous(api_client, current)

    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_student_cannot_view_previous_lesson(api_client, student, make_booking):
    current = make_booking(at(10, 25), at(12))
    api_client.force_authenticate(user=student)

    assert get_previous(api_client, current).status_code == status.HTTP_403_FORBIDDEN


def test_anonymous_cannot_view_previous_lesson(api_client, make_booking):
    current = make_booking(at(10, 25), at(12))

    assert get_previous(api_client, current).status_code == status.HTTP_403_FORBIDDEN


def test_unknown_booking_returns_404(api_client, teacher):
    api_client.force_authenticate(user=teacher)

    response = api_client.get(reverse("booking-previous", args=[uuid.uuid4()]))

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_cancelled_booking_returns_409(api_client, teacher, make_booking):
    current = make_booking(at(10, 25), at(12), status=Booking.BookingStatus.CANCELLED)
    api_client.force_authenticate(user=teacher)

    response = get_previous(api_client, current)

    assert response.status_code == status.HTTP_409_CONFLICT


def test_endpoint_is_read_only(api_client, teacher, make_booking):
    current = make_booking(at(10, 25), at(12))
    api_client.force_authenticate(user=teacher)

    response = api_client.post(reverse("booking-previous", args=[current.id]), {}, format="json")

    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


def test_lookup_uses_constant_number_of_queries(
    api_client, teacher, make_booking, book_previous, room, django_assert_max_num_queries
):
    book_previous(at(8, 30), at(10, 5), in_room=room)
    current = make_booking(at(10, 25), at(12))
    api_client.force_authenticate(user=teacher)

    with django_assert_max_num_queries(3):
        response = get_previous(api_client, current)

    assert response.status_code == status.HTTP_200_OK
