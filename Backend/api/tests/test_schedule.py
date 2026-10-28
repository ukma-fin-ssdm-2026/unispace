"""
Тести розкладу (FR-006, FR-007, US-05): TP-13.

Студент бачить розклад своєї групи, викладач - власні заняття, диспетчер - будь-які.
Тести працюють зі справжньою базою PostgreSQL (див. conftest.py).

Примітка щодо використання ШІ: тести написано з допомогою ШІ (Claude) за api/views.py;
запуск `pytest` локально і в CI виконує автор PR.
"""

from datetime import date

from unittest.mock import patch

import pytest
from django.urls import reverse
from rest_framework import status

from api.models import AcademicGroup, Booking, AuditLog

from .conftest import at

pytestmark = [pytest.mark.django_db, pytest.mark.req("US-05")]

# ==========================================
# Фікстури та Хелпери
# ==========================================


@pytest.fixture
def other_group(db):
    return AcademicGroup.objects.create(name="ІПЗ-4", source_key="group-ipz-4")


def log_room_change(booking, user, previous_room, new_room, when):
    """Запис аудиту із заданим часом: created_at проставляється автоматично, тому підміняємо поточний час."""
    with patch("django.utils.timezone.now", return_value=when):
        return AuditLog.objects.create(
            booking=booking,
            user=user,
            action="room_changed",
            previous_room=previous_room,
            new_room=new_room,
        )


def get_schedule(client, **params):
    return client.get(reverse("schedule"), params)


def lesson_ids(response):
    return {item["lesson_id"] for item in response.json()}

    # ==========================================
    # Видимість розкладу за ролями (Permissions)
    # ==========================================


def test_student_sees_lessons_of_own_group(api_client, student, make_lesson):
    own_lesson = make_lesson(at(10), at(11, 30))
    api_client.force_authenticate(user=student)

    response = get_schedule(api_client)

    assert response.status_code == status.HTTP_200_OK
    assert lesson_ids(response) == {str(own_lesson.id)}


def test_student_does_not_see_lessons_of_other_group(api_client, student, make_lesson, other_group):
    make_lesson(at(10), at(11, 30), lesson_group=other_group)
    api_client.force_authenticate(user=student)

    response = get_schedule(api_client)

    assert response.json() == []


def test_teacher_sees_only_own_lessons(api_client, teacher, other_teacher, make_lesson):
    own_lesson = make_lesson(at(10), at(11, 30))
    make_lesson(at(12), at(13, 30), lesson_teacher=other_teacher)
    api_client.force_authenticate(user=teacher)

    response = get_schedule(api_client)

    assert lesson_ids(response) == {str(own_lesson.id)}


def test_dispatcher_sees_all_lessons(api_client, dispatcher, other_teacher, make_lesson, other_group):
    first = make_lesson(at(10), at(11, 30))
    second = make_lesson(at(12), at(13, 30), lesson_teacher=other_teacher, lesson_group=other_group)
    api_client.force_authenticate(user=dispatcher)

    response = get_schedule(api_client)

    assert lesson_ids(response) == {str(first.id), str(second.id)}


def test_anonymous_cannot_view_schedule(api_client):
    response = get_schedule(api_client)

    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_schedule_is_read_only_for_students(api_client, student):
    api_client.force_authenticate(user=student)

    response = api_client.post(reverse("schedule"), {}, format="json")

    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    # ==========================================
    # Фільтрація, Сортування та Пагінація
    # ==========================================


def test_student_ignores_group_filter(api_client, student, make_lesson, other_group):
    own_lesson = make_lesson(at(10), at(11, 30))
    make_lesson(at(12), at(13, 30), lesson_group=other_group)
    api_client.force_authenticate(user=student)

    response = get_schedule(api_client, group_id=other_group.id)

    assert lesson_ids(response) == {str(own_lesson.id)}


def test_dispatcher_filters_schedule_by_group(api_client, dispatcher, make_lesson, other_group):
    make_lesson(at(10), at(11, 30))
    other_lesson = make_lesson(at(12), at(13, 30), lesson_group=other_group)
    api_client.force_authenticate(user=dispatcher)

    response = get_schedule(api_client, group_id=other_group.id)

    assert lesson_ids(response) == {str(other_lesson.id)}


def test_schedule_is_filtered_by_date_range(api_client, student, make_lesson):
    make_lesson(at(10), at(11, 30))
    second_day = make_lesson(at(10, day=date(2026, 10, 21)), at(11, 30, day=date(2026, 10, 21)))
    api_client.force_authenticate(user=student)

    response = get_schedule(api_client, date_from="2026-10-21", date_to="2026-10-21")

    assert lesson_ids(response) == {str(second_day.id)}


def test_schedule_is_ordered_by_date_and_time(api_client, student, make_lesson):
    late = make_lesson(at(14), at(15, 30))
    early = make_lesson(at(8, 30), at(10))
    api_client.force_authenticate(user=student)

    response = get_schedule(api_client)

    assert [item["lesson_id"] for item in response.json()] == [str(early.id), str(late.id)]


def test_schedule_respects_limit_and_offset(api_client, student, make_lesson):
    make_lesson(at(8, 30), at(10))
    second = make_lesson(at(10, 30), at(12))
    api_client.force_authenticate(user=student)

    response = get_schedule(api_client, limit=1, offset=1)

    assert lesson_ids(response) == {str(second.id)}


def test_date_from_after_date_to_returns_400(api_client, student):
    api_client.force_authenticate(user=student)

    response = get_schedule(api_client, date_from="2026-10-22", date_to="2026-10-21")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_invalid_group_id_returns_400(api_client, dispatcher):
    api_client.force_authenticate(user=dispatcher)

    response = get_schedule(api_client, group_id="not-a-uuid")

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_limit_zero_returns_400(api_client, student):
    api_client.force_authenticate(user=student)

    response = get_schedule(api_client, limit=0)

    assert response.status_code == status.HTTP_400_BAD_REQUEST

    # ==========================================
    # Формат відповіді та Маркери змін
    # ==========================================


def test_schedule_item_contains_lesson_and_room_details(api_client, student, room, make_booking):
    make_booking(at(10), at(11, 30))
    api_client.force_authenticate(user=student)

    item = get_schedule(api_client).json()[0]

    assert item["subject"] == "Програмна інженерія"
    assert item["date"] == "2026-10-20"
    assert item["start_time"] == "10:00:00"
    assert item["end_time"] == "11:30:00"
    assert item["group"] == "ІПЗ-3"
    assert item["teacher"] == "Тестовий Викладач"
    assert item["room"] == {"id": str(room.id), "building": "1", "number": "1-225"}
    assert item["room_assigned"] is True
    assert item["room_changed"] is False


def test_schedule_shows_new_room_after_change(api_client, student, other_room, make_booking):
    booking = make_booking(at(10), at(11, 30))
    booking.room = other_room
    booking.save()
    api_client.force_authenticate(user=student)

    item = get_schedule(api_client).json()[0]

    assert item["room"]["number"] == "1-226"


def test_cancelled_booking_keeps_lesson_without_room(api_client, student, make_booking):
    make_booking(at(10), at(11, 30), status=Booking.BookingStatus.CANCELLED)
    api_client.force_authenticate(user=student)

    item = get_schedule(api_client).json()[0]

    assert item["room"] is None
    assert item["room_assigned"] is False


def test_lesson_without_booking_has_no_room(api_client, student, make_lesson):
    make_lesson(at(10), at(11, 30))
    api_client.force_authenticate(user=student)

    item = get_schedule(api_client).json()[0]

    assert item["room"] is None
    assert item["room_assigned"] is False


def test_room_changed_marker_is_set_when_changed_within_24_hours_before_start(
    api_client, student, teacher, room, other_room, make_booking
):
    booking = make_booking(at(10), at(11, 30))
    log_room_change(booking, teacher, room, other_room, at(12, day=date(2026, 10, 19)))
    api_client.force_authenticate(user=student)

    item = get_schedule(api_client).json()[0]

    assert item["room_changed"] is True


def test_room_changed_marker_is_not_set_for_old_change(api_client, student, teacher, room, other_room, make_booking):
    booking = make_booking(at(10), at(11, 30))
    log_room_change(booking, teacher, room, other_room, at(12, day=date(2026, 10, 15)))
    api_client.force_authenticate(user=student)

    item = get_schedule(api_client).json()[0]

    assert item["room_changed"] is False


def test_room_changed_marker_is_not_set_without_changes(api_client, student, make_booking):
    make_booking(at(10), at(11, 30))
    api_client.force_authenticate(user=student)

    item = get_schedule(api_client).json()[0]

    assert item["room_changed"] is False
