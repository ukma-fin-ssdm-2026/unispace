"""
Тести сервісної функції send_room_change_emails (FR-015, US-07): граничні та негативні випадки.

Сценарії «зверху вниз» через API (кому і що надсилається) покриває test_email_notifications.py (TP-24).
Тут функція викликається напряму, щоб перевірити те, що через API відтворити важко:
межу дати початку семестру, відсутність одержувачів і поведінку при збої SMTP.

Примітка щодо використання ШІ: тести написано з допомогою ШІ (Claude) за FR-015 і коментарями в
api/services/notifications.py; перед PR автор запускає pytest локально.
"""

import logging
import smtplib
from datetime import date
from unittest.mock import patch

import pytest

from api.models import AcademicGroup, Booking, User
from api.services.notifications import send_room_change_emails
from api.tests.conftest import at

pytestmark = [pytest.mark.django_db, pytest.mark.req("US-07")]

SEMESTER_START = date(2026, 9, 1)


# ==========================================
# Кількість листів і одержувачі
# ==========================================


def test_returns_number_of_sent_emails(student, make_booking, room, other_room, mailoutbox):
    User.objects.create(email="student2@ukma.edu.ua", role="student", group=student.group)
    booking = make_booking(at(10), at(11, 30))

    sent = send_room_change_emails(booking, room, other_room)

    assert sent == 2
    assert len(mailoutbox) == 2


def test_group_without_active_students_gets_no_emails(student, make_booking, room, other_room, mailoutbox):
    student.is_active = False
    student.save()
    booking = make_booking(at(10), at(11, 30))

    with patch("api.services.notifications.send_mass_mail") as send_mass_mail:
        sent = send_room_change_emails(booking, room, other_room)

    assert sent == 0
    send_mass_mail.assert_not_called()
    assert len(mailoutbox) == 0


def test_empty_group_gets_no_emails(teacher, make_lesson, room, other_room, mailoutbox):
    empty_group = AcademicGroup.objects.create(name="ІПЗ-0", source_key="group-ipz-0")
    lesson = make_lesson(at(10), at(11, 30), lesson_group=empty_group)
    booking = Booking.objects.create(lesson=lesson, room=room)

    assert send_room_change_emails(booking, room, other_room) == 0
    assert len(mailoutbox) == 0


# ==========================================
# Межа початку семестру (включно)
# ==========================================


@pytest.mark.parametrize(
    ("today", "expected_emails"),
    [
        (date(2026, 8, 31), 0),  # за день до початку семестру
        (date(2026, 9, 1), 1),  # у перший день семестру лист уже йде (межа включно)
        (date(2026, 9, 2), 1),  # після початку
    ],
    ids=["day-before", "first-day", "day-after"],
)
def test_email_respects_semester_start_boundary(
    student, make_booking, room, other_room, mailoutbox, settings, today, expected_emails
):
    settings.SEMESTER_START_DATE = SEMESTER_START
    booking = make_booking(at(10), at(11, 30))

    with patch("api.services.notifications.timezone.localdate", return_value=today):
        sent = send_room_change_emails(booking, room, other_room)

    assert sent == expected_emails
    assert len(mailoutbox) == expected_emails


def test_email_is_sent_when_semester_start_is_not_configured(
    student, make_booking, room, other_room, mailoutbox, settings
):
    settings.SEMESTER_START_DATE = None
    booking = make_booking(at(10), at(11, 30))

    assert send_room_change_emails(booking, room, other_room) == 1
    assert len(mailoutbox) == 1


# ==========================================
# Збої SMTP
# ==========================================


@pytest.mark.parametrize(
    "error",
    [smtplib.SMTPServerDisconnected("з'єднання розірвано"), TimeoutError("таймаут"), ConnectionRefusedError("відмова")],
    ids=["smtp-exception", "timeout", "connection-refused"],
)
def test_smtp_and_network_errors_are_logged_and_swallowed(
    student, make_booking, room, other_room, mailoutbox, caplog, error
):
    booking = make_booking(at(10), at(11, 30))

    with patch("api.services.notifications.send_mass_mail", side_effect=error):
        with caplog.at_level(logging.ERROR, logger="api.services.notifications"):
            sent = send_room_change_emails(booking, room, other_room)

    assert sent == 0
    assert len(mailoutbox) == 0
    assert any(str(booking.lesson_id) in record.getMessage() for record in caplog.records)
