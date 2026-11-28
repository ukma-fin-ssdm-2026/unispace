"""
Тести внутрішніх сповіщень про зміну аудиторії (FR-015, US-07; TP-02).

Сповіщення створюються в тій самій транзакції, що й перенесення
(api/services/bookings.py::_notify_group), тому тести перевіряють і одержувачів, і відкат.

Примітка щодо використання ШІ: тести написано з допомогою ШІ (Claude) за FR-015 і US-07;
перед PR автор запускає pytest локально.
"""

import pytest
from django.urls import reverse
from rest_framework import status

from api.models import AcademicGroup, Notification, User
from api.tests.conftest import at

pytestmark = [pytest.mark.django_db, pytest.mark.req("US-07")]


@pytest.fixture
def teacher_client(api_client, teacher):
    api_client.force_authenticate(user=teacher)
    return api_client


def post_change(client, booking, room):
    return client.post(
        reverse("booking-change-room", args=[booking.id]),
        {"room_id": str(room.id), "reason": "Ремонт"},
        format="json",
    )


def test_every_group_member_gets_exactly_one_notification(teacher_client, student, group, make_booking, other_room):
    second_student = User.objects.create(email="student2@ukma.edu.ua", role="student", group=group)
    booking = make_booking(at(10), at(11, 30))

    response = post_change(teacher_client, booking, other_room)

    assert response.status_code == status.HTTP_200_OK
    assert Notification.objects.filter(user=student, type="room_changed").count() == 1
    assert Notification.objects.filter(user=second_student, type="room_changed").count() == 1
    assert Notification.objects.count() == 2


def test_students_of_other_groups_get_no_notification(teacher_client, student, make_booking, other_room):
    other_group = AcademicGroup.objects.create(name="ІПЗ-9", source_key="group-ipz-9")
    outsider = User.objects.create(email="outsider@ukma.edu.ua", role="student", group=other_group)
    booking = make_booking(at(10), at(11, 30))

    post_change(teacher_client, booking, other_room)

    assert not Notification.objects.filter(user=outsider).exists()
    assert Notification.objects.filter(user=student).count() == 1


def test_notification_text_has_subject_time_and_both_rooms(teacher_client, student, make_booking, room, other_room):
    booking = make_booking(at(10), at(11, 30))

    post_change(teacher_client, booking, other_room)

    message = Notification.objects.get(user=student).message
    for fragment in ("Програмна інженерія", "20.10.2026 10:00", room.number, other_room.number):
        assert fragment in message
    assert message.index(room.number) < message.index(other_room.number)  # «було → стало»


def test_failed_room_change_creates_no_notifications(teacher_client, student, make_booking, room, other_room):
    make_booking(at(10), at(11, 30), booking_room=other_room)
    booking = make_booking(at(10), at(11, 30), booking_room=room)

    response = post_change(teacher_client, booking, other_room)

    assert response.status_code == status.HTTP_409_CONFLICT
    assert Notification.objects.count() == 0


def test_change_to_same_room_creates_no_notifications(teacher_client, student, make_booking, room):
    booking = make_booking(at(10), at(11, 30))

    response = post_change(teacher_client, booking, room)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert Notification.objects.count() == 0


def test_student_cannot_trigger_notifications(api_client, student, make_booking, other_room):
    booking = make_booking(at(10), at(11, 30))
    api_client.force_authenticate(user=student)

    response = post_change(api_client, booking, other_room)

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert Notification.objects.count() == 0
