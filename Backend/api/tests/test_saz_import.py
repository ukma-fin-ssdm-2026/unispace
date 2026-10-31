"""
Тести імпорту розкладу САЗ (FR-004), ручної синхронізації (FR-005) і збереження даних
при невдалій спробі (REL-002). Фікстура: fixtures/saz/schedule_preview.html (анонімізована).

Розклад фікстури (тиждень 1 починається 31.08.2026):
- Пн 8:30 лекція «Алгоритми» тижні 2-4, ауд. 1-223; Пн 10:00 гр.1 тижні 2-3, ауд. 1-225 (гібридно);
- Пн 13:30 гр.2 тижні 2,4 дистанційно; Вт 10:00 лекція і гр.2 в одній ауд. 1-223 тижні 2-3 (накладка);
- Вт 11:40 гр.1 тижні 2-3 в ауд. «10к», якої немає в довіднику.

Примітка щодо використання ШІ: тести згенеровано ШІ (Claude), переглянуто автором PR.
"""

from datetime import date, time
from pathlib import Path

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status

from api.models import AcademicGroup, Booking, Conflict, Lesson, Room, SyncLog, User
from api.services.saz_import import import_schedule, run_sync
from api.services.saz_parser import parse_schedule

pytestmark = [pytest.mark.django_db, pytest.mark.req("FR-004")]

HTML = (Path(__file__).parent / "fixtures" / "saz" / "schedule_preview.html").read_text(encoding="utf-8")
SEMESTER_START = date(2026, 9, 1)  # вівторок першого тижня; понеділок тижня 1 - 31.08.2026


@pytest.fixture
def saz_rooms(db):
    """Аудиторії довідника: номер записано в обох уживаних форматах («223» і «1-225»)."""
    return {
        "1-223": Room.objects.create(building="1", number="223", capacity=60),
        "1-225": Room.objects.create(building="1", number="1-225", capacity=30),
    }


def run_import():
    return import_schedule(parse_schedule(HTML), SEMESTER_START)


def test_each_week_becomes_a_lesson_on_the_right_date(saz_rooms):
    # Act
    result = run_import()

    # Assert: 3 + 2 + 2 + 2 + 2 + 2 заняття
    assert result.lessons_created == 13
    lecture = Lesson.objects.filter(subject="Алгоритми", start_time=time(8, 30)).order_by("date")
    assert [lesson.date for lesson in lecture] == [date(2026, 9, 7), date(2026, 9, 14), date(2026, 9, 21)]


def test_groups_and_teachers_are_created_from_schedule(saz_rooms):
    # Act
    result = run_import()

    # Assert
    names = set(AcademicGroup.objects.values_list("name", flat=True))
    assert "Тестова інженерія, 3 р.н. (лекційний потік)" in names
    assert "Тестова інженерія, 3 р.н., група 1" in names
    assert result.teachers_created == 4
    teacher = User.objects.get(full_name="А.А. Альфа")
    assert teacher.role == User.RoleChoices.TEACHER
    assert teacher.email.endswith("@saz.invalid")
    assert not teacher.has_usable_password()


def test_existing_teacher_is_matched_by_full_name(saz_rooms):
    # Arrange: викладач уже є в UniSpace (наприклад, увійшов через Microsoft)
    known = User.objects.create(email="alpha@ukma.edu.ua", full_name="А.А. Альфа", role="teacher")

    # Act
    run_import()

    # Assert
    lecture = Lesson.objects.filter(subject="Алгоритми", start_time=time(8, 30))
    assert set(lecture.values_list("teacher", flat=True)) == {known.pk}


def test_default_bookings_are_created_only_for_rooms_in_directory(saz_rooms):
    # Act
    result = run_import()

    # Assert: лекція Пн (3) + гр.1 Пн (2) + лекція Вт (2); дистанційні й «10к» без бронювань
    assert result.bookings_created == 7
    assert Booking.objects.filter(source=Booking.BookingSource.SAZ).count() == 7
    assert not Booking.objects.filter(lesson__start_time=time(13, 30)).exists()
    assert result.online_lessons == 2


def test_unknown_room_is_reported_as_warning(saz_rooms):
    # Act
    result = run_import()

    # Assert
    assert "Аудиторію «10к» не знайдено в довіднику: заняття імпортовано без бронювання" in result.warnings
    assert "Рядок 15: Не вдалося розпізнати тижні: за потреби" in result.warnings


def test_overlapping_lessons_in_same_room_are_recorded_as_conflicts(saz_rooms):
    # Act
    result = run_import()

    # Assert: Вт 10:00 лекція і група 2 в ауд. 1-223 у тижні 2 і 3
    assert result.conflicts_created == 2
    conflict = Conflict.objects.order_by("overlap_start").first()
    assert conflict.room == saz_rooms["1-223"]
    assert conflict.status == Conflict.ConflictStatus.OPEN
    assert {conflict.first_lesson.subject, conflict.second_lesson.subject} == {"Бази даних", "Алгоритми"}


def test_repeated_import_creates_no_duplicates(saz_rooms):
    # Arrange
    run_import()
    counts = (Lesson.objects.count(), Booking.objects.count(), Conflict.objects.count(), User.objects.count())

    # Act
    result = run_import()

    # Assert
    assert result.lessons_created == 0
    assert result.lessons_updated == 13
    assert result.bookings_created == 0
    assert (Lesson.objects.count(), Booking.objects.count(), Conflict.objects.count(), User.objects.count()) == counts


def test_reimport_keeps_room_changed_by_teacher(saz_rooms):
    # Arrange: після імпорту заняття перенесли в іншу аудиторію
    run_import()
    booking = Booking.objects.filter(room=saz_rooms["1-225"]).first()
    other = Room.objects.create(building="1", number="1-400", capacity=30)
    booking.room = other
    booking.save()

    # Act
    run_import()

    # Assert
    booking.refresh_from_db()
    assert booking.room == other


@pytest.mark.req("FR-005", "REL-002")
def test_failed_sync_is_logged_and_keeps_previously_imported_data(saz_rooms):
    # Arrange
    run_import()
    lessons_before = Lesson.objects.count()

    # Act: САЗ змінив розмітку (або збережено не ту сторінку)
    log, result = run_sync("<html><body>Сторінка входу</body></html>", SEMESTER_START)

    # Assert
    assert result is None
    assert log.status == SyncLog.SyncStatus.FAILED
    assert "Таблицю розкладу САЗ не знайдено" in log.error_message
    assert log.finished_at is not None
    assert Lesson.objects.count() == lessons_before


# --- POST /api/v1/sync/ ---


def upload(client, content=HTML, **extra):
    data = {"file": SimpleUploadedFile("schedule.html", content.encode("utf-8"), content_type="text/html")}
    data.update(extra)
    return client.post(reverse("sync-trigger"), data, format="multipart")


@pytest.mark.req("FR-005")
def test_dispatcher_imports_schedule_and_sees_result(api_client, dispatcher, saz_rooms):
    # Arrange
    api_client.force_authenticate(user=dispatcher)

    # Act
    response = upload(api_client, semester_start="2026-09-01")

    # Assert
    body = response.json()
    assert response.status_code == status.HTTP_201_CREATED
    assert body["status"] == "success"
    assert body["summary"]["lessons_created"] == 13
    assert body["summary"]["conflicts_created"] == 2
    assert SyncLog.objects.get(pk=body["id"]).status == SyncLog.SyncStatus.SUCCESS


@pytest.mark.req("FR-005")
def test_unrecognized_page_returns_failed_sync_result(api_client, dispatcher):
    # Arrange
    api_client.force_authenticate(user=dispatcher)

    # Act
    response = upload(api_client, content="<html>не розклад</html>", semester_start="2026-09-01")

    # Assert
    body = response.json()
    assert response.status_code == status.HTTP_201_CREATED
    assert body["status"] == "failed"
    assert body["summary"] is None
    assert body["error_message"]


@pytest.mark.req("FR-005")
def test_semester_start_is_required(api_client, dispatcher):
    # Arrange
    api_client.force_authenticate(user=dispatcher)

    # Act
    response = upload(api_client)

    # Assert
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["error"]["details"][0]["field"] == "semester_start"


@pytest.mark.req("FR-005")
@pytest.mark.parametrize("role", ["teacher", "student"])
def test_only_dispatcher_can_import_schedule(api_client, role):
    # Arrange
    user = User.objects.create(email=f"{role}-sync@ukma.edu.ua", role=role)
    api_client.force_authenticate(user=user)

    # Act
    response = upload(api_client, semester_start="2026-09-01")

    # Assert
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert not Lesson.objects.exists()
