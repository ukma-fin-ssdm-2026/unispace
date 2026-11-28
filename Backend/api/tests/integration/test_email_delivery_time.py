"""
Тест часу доставки email про зміну аудиторії (NFR PERF-002, TP-07).

PERF-002: 95% листів мають бути передані на SMTP не пізніше ніж за 2 хвилини після успішного
збереження зміни в БД. Лист іде через transaction.on_commit() (api/services/bookings.py), тож тест
перевіряє дві речі: (1) до коміту лист не передається, (2) p95 затримки від початку запиту
до передачі листа поштовому бекенду не перевищує порогу.

Обмеження: вимірюється час у застосунку до передачі бекенду (SMTP-з'єднання замінює тестовий
бекенд з відміткою часу), а не мережева доставка до поштової скриньки. Тест ловить регресії
на кшталт синхронних повторів, затримок і зайвої роботи між комітом і відправкою.

Примітка щодо використання ШІ: тест написано з допомогою ШІ (Claude) за PERF-002 і TP-07;
перед PR автор запускає pytest локально.
"""

import math
import time
from datetime import date, timedelta

import pytest
from django.core.mail.backends.locmem import EmailBackend
from django.urls import reverse
from rest_framework import status

from api.models import User
from api.tests.conftest import at

pytestmark = [pytest.mark.django_db, pytest.mark.req("PERF-002")]

PERF_002_LIMIT_SECONDS = 120  # 2 хвилини
EVENTS = 20  # кількість змін аудиторії (окремих подій)
STUDENTS = 3  # одержувачів у групі, тож листів EVENTS * STUDENTS

SENT_AT = []


class TimestampedEmailBackend(EmailBackend):
    """Тестовий SMTP-бекенд: кладе листи в mail.outbox і запам'ятовує момент передачі кожного."""

    def send_messages(self, messages):
        moment = time.perf_counter()
        SENT_AT.extend([moment] * len(messages))
        return super().send_messages(messages)


@pytest.fixture(autouse=True)
def timestamped_backend(settings):
    SENT_AT.clear()
    settings.EMAIL_BACKEND = f"{__name__}.TimestampedEmailBackend"
    settings.SEMESTER_START_DATE = None
    yield
    SENT_AT.clear()


@pytest.fixture
def students(group):
    return [User.objects.create(email=f"student{n}@ukma.edu.ua", role="student", group=group) for n in range(STUDENTS)]


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


def percentile_95(values):
    """Найближчий ранг: найменше значення, не більше за яке 95% вибірки."""
    ordered = sorted(values)
    return ordered[math.ceil(0.95 * len(ordered)) - 1]


def test_email_is_not_handed_to_smtp_before_commit(
    teacher_client, students, make_booking, other_room, django_capture_on_commit_callbacks
):
    booking = make_booking(at(10), at(11, 30))

    with django_capture_on_commit_callbacks(execute=False) as callbacks:
        response = post_change(teacher_client, booking, other_room)

    assert response.status_code == status.HTTP_200_OK
    assert SENT_AT == []  # транзакція ще не закомічена
    assert callbacks  # відправку відкладено через transaction.on_commit()

    for callback in callbacks:
        callback()

    assert len(SENT_AT) == STUDENTS


def test_p95_of_email_delay_after_room_change_is_within_two_minutes(
    teacher_client, students, make_booking, other_room, mailoutbox, django_capture_on_commit_callbacks
):
    first_day = date(2026, 10, 1)
    delays = []

    for event in range(EVENTS):
        booking = make_booking(
            at(10, day=first_day + timedelta(days=event)), at(11, 30, day=first_day + timedelta(days=event))
        )
        before = len(SENT_AT)
        started = time.perf_counter()

        with django_capture_on_commit_callbacks(execute=True):
            response = post_change(teacher_client, booking, other_room)

        assert response.status_code == status.HTTP_200_OK
        delays.extend(moment - started for moment in SENT_AT[before:])

    assert len(delays) == EVENTS * STUDENTS == len(mailoutbox)
    assert all(delay >= 0 for delay in delays)
    assert percentile_95(delays) <= PERF_002_LIMIT_SECONDS
