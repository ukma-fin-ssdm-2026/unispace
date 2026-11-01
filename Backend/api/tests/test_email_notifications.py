"""
Тести email-сповіщень про зміну аудиторії (FR-015, US-07): TP-24.

Лист іде кожному активному студенту групи після успішного збереження перенесення
(POST /api/v1/bookings/{id}/change/). Тести працюють зі справжньою базою PostgreSQL.
Колбеки transaction.on_commit у тестах виконує django_capture_on_commit_callbacks.

Примітка щодо використання ШІ: тести написано з допомогою ШІ (Claude) за FR-015 і US-07;
запуск `pytest` локально і в CI виконує автор PR.
"""

from datetime import date
from unittest.mock import patch

import pytest
from django.urls import reverse
from rest_framework import status

from api.models import AcademicGroup, Notification, User

from .conftest import at

pytestmark = [pytest.mark.django_db, pytest.mark.req("US-07")]

# ==========================================
# Фікстури та Хелпери
# ==========================================


@pytest.fixture
def second_student(group):
    return User.objects.create(email="student2@ukma.edu.ua", full_name="Другий Студент", role="student", group=group)


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


# ==========================================
# Кому і що надсилається
# ==========================================


def test_every_student_of_group_gets_own_email_with_required_fields(
    teacher_client,
    teacher,
    student,
    second_student,
    make_booking,
    other_room,
    mailoutbox,
    settings,
    django_capture_on_commit_callbacks,
):
    booking = make_booking(at(10), at(11, 30))

    with django_capture_on_commit_callbacks(execute=True):
        response = post_change(teacher_client, booking, other_room)

    assert response.status_code == status.HTTP_200_OK
    assert {message.to[0] for message in mailoutbox} == {student.email, second_student.email}
    assert all(len(message.to) == 1 for message in mailoutbox)
    message = mailoutbox[0]
    assert message.from_email == settings.DEFAULT_FROM_EMAIL
    assert "Програмна інженерія" in message.subject
    for fragment in ("Програмна інженерія", "1-226", teacher.full_name, "20.10.2026 10:00"):
        assert fragment in message.body


def test_students_of_other_groups_and_inactive_students_get_no_email(
    teacher_client,
    student,
    second_student,
    make_booking,
    other_room,
    mailoutbox,
    django_capture_on_commit_callbacks,
):
    other_group = AcademicGroup.objects.create(name="ІПЗ-9", source_key="group-ipz-9")
    User.objects.create(email="outsider@ukma.edu.ua", role="student", group=other_group)
    second_student.is_active = False
    second_student.save()
    booking = make_booking(at(10), at(11, 30))

    with django_capture_on_commit_callbacks(execute=True):
        post_change(teacher_client, booking, other_room)

    assert [message.to[0] for message in mailoutbox] == [student.email]


def test_line_breaks_in_lesson_subject_do_not_break_email(
    teacher_client, student, make_booking, other_room, mailoutbox, django_capture_on_commit_callbacks
):
    booking = make_booking(at(10), at(11, 30))
    booking.lesson.subject = "Бази\nданих"
    booking.lesson.save()

    with django_capture_on_commit_callbacks(execute=True):
        response = post_change(teacher_client, booking, other_room)

    assert response.status_code == status.HTTP_200_OK
    assert len(mailoutbox) == 1
    assert "Бази даних" in mailoutbox[0].subject
    assert "\n" not in mailoutbox[0].subject


# ==========================================
# Коли лист не надсилається
# ==========================================


def test_no_email_when_room_change_fails(
    teacher_client, student, make_booking, room, other_room, mailoutbox, django_capture_on_commit_callbacks
):
    make_booking(at(10), at(11, 30), booking_room=other_room)
    booking = make_booking(at(10), at(11, 30), booking_room=room)

    with django_capture_on_commit_callbacks(execute=True):
        response = post_change(teacher_client, booking, other_room)

    assert response.status_code == status.HTTP_409_CONFLICT
    assert len(mailoutbox) == 0


def test_no_email_before_semester_start_but_in_app_notification_is_created(
    teacher_client, student, make_booking, other_room, mailoutbox, settings, django_capture_on_commit_callbacks
):
    settings.SEMESTER_START_DATE = date(2999, 1, 1)
    booking = make_booking(at(10), at(11, 30))

    with django_capture_on_commit_callbacks(execute=True):
        response = post_change(teacher_client, booking, other_room)

    assert response.status_code == status.HTTP_200_OK
    assert len(mailoutbox) == 0
    assert Notification.objects.filter(user=student, type="room_changed").count() == 1


def test_email_is_sent_after_semester_start(
    teacher_client, student, make_booking, other_room, mailoutbox, settings, django_capture_on_commit_callbacks
):
    settings.SEMESTER_START_DATE = date(2000, 1, 1)
    booking = make_booking(at(10), at(11, 30))

    with django_capture_on_commit_callbacks(execute=True):
        post_change(teacher_client, booking, other_room)

    assert len(mailoutbox) == 1


# ==========================================
# Збій SMTP
# ==========================================


def test_smtp_failure_does_not_break_room_change(
    teacher_client, student, make_booking, other_room, django_capture_on_commit_callbacks
):
    booking = make_booking(at(10), at(11, 30))

    with patch("api.services.notifications.send_mass_mail", side_effect=OSError("SMTP недоступний")):
        with django_capture_on_commit_callbacks(execute=True):
            response = post_change(teacher_client, booking, other_room)

    assert response.status_code == status.HTTP_200_OK
    booking.refresh_from_db()
    assert booking.room_id == other_room.id
    assert Notification.objects.filter(user=student, type="room_changed").count() == 1
