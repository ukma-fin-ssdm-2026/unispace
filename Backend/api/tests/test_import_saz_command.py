"""
Характеризаційні тести команди `python manage.py import_saz` (FR-004, FR-005) перед рефакторингом Лаб 8.

До Лаб 8 команда не мала жодного тесту (0% покриття). Тести фіксують її поточну поведінку,
зокрема ту, що виглядає дивно, щоб рефакторинг можна було перевірити: ті самі тести мають бути
зеленими до і після. Дивні, але зафіксовані особливості:
- лічильник online_lessons рахується, але не друкується;
- існування файлу перевіряється раніше за дату семестру;
- невалідні байти UTF-8 у файлі замінюються, а не валять імпорт (errors="replace");
- при нерозпізнаній сторінці команда падає з CommandError, але запис failed у SyncLog лишається.

Фікстура: fixtures/saz/schedule_preview.html (анонімізована), та сама, що в test_saz_import.py.

Примітка щодо використання ШІ: тести написано з допомогою ШІ (Claude) за кодом
api/management/commands/import_saz.py; запуск `pytest` локально і в CI виконує авторка PR (Ольга Михайлик).
"""

from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from api.models import Lesson, Room, SyncLog

pytestmark = [pytest.mark.django_db, pytest.mark.req("FR-004")]

FIXTURE = Path(__file__).parent / "fixtures" / "saz" / "schedule_preview.html"
SEMESTER_START = "2026-09-01"
COUNT_LINES = [
    "lessons_created: 13",
    "lessons_updated: 0",
    "bookings_created: 7",
    "conflicts_created: 2",
    "teachers_created: 4",
]


@pytest.fixture
def saz_rooms(db):
    """Ті самі аудиторії довідника, що й у test_saz_import.py."""
    Room.objects.create(building="1", number="223", capacity=60)
    Room.objects.create(building="1", number="1-225", capacity=30)


def run_command(path=FIXTURE, semester_start=SEMESTER_START):
    out = StringIO()
    call_command("import_saz", str(path), "--semester-start", semester_start, stdout=out)
    return out.getvalue().splitlines()


def test_prints_five_counters_in_fixed_order_and_finishes_with_success(saz_rooms):
    # Act
    lines = run_command()

    # Assert
    assert lines[:5] == COUNT_LINES
    assert lines[-1] == "Імпорт завершено"


def test_online_lessons_counter_is_not_printed(saz_rooms):
    # Act
    lines = run_command()

    # Assert: імпорт рахує 2 онлайн-заняття, але команда цей лічильник не виводить
    assert not any(line.startswith("online_lessons") for line in lines)


def test_warnings_are_printed_between_counters_and_final_line(saz_rooms):
    # Act
    lines = run_command()

    # Assert
    warnings = lines[5:-1]
    assert "Аудиторію «10к» не знайдено в довіднику: заняття імпортовано без бронювання" in warnings
    assert "Рядок 15: Не вдалося розпізнати тижні: за потреби" in warnings


@pytest.mark.req("FR-005")
def test_successful_import_writes_one_success_sync_log_with_manual_trigger(saz_rooms):
    # Act
    run_command()

    # Assert
    log = SyncLog.objects.get()
    assert log.status == SyncLog.SyncStatus.SUCCESS
    assert log.trigger == SyncLog.SyncTrigger.MANUAL
    assert log.finished_at is not None


def test_repeated_import_reports_updated_lessons(saz_rooms):
    # Arrange
    run_command()

    # Act
    lines = run_command()

    # Assert
    assert lines[:3] == ["lessons_created: 0", "lessons_updated: 13", "bookings_created: 0"]
    assert Lesson.objects.count() == 13


def test_missing_file_raises_command_error_without_sync_log(tmp_path):
    # Act / Assert
    with pytest.raises(CommandError, match="^Файл не знайдено: "):
        run_command(path=tmp_path / "missing.html")
    assert not SyncLog.objects.exists()


def test_invalid_semester_start_raises_command_error_without_sync_log():
    # Act / Assert
    with pytest.raises(CommandError, match="^--semester-start має бути датою РРРР-ММ-ДД$"):
        run_command(semester_start="01.09.2026")
    assert not SyncLog.objects.exists()


def test_missing_file_is_reported_before_invalid_date(tmp_path):
    # Act / Assert: обидва аргументи погані, але повідомлення - лише про файл
    with pytest.raises(CommandError, match="^Файл не знайдено: "):
        run_command(path=tmp_path / "missing.html", semester_start="not-a-date")


def test_missing_semester_start_option_is_rejected_by_argument_parser():
    # Act / Assert
    with pytest.raises(CommandError, match="--semester-start"):
        call_command("import_saz", str(FIXTURE), stdout=StringIO())


@pytest.mark.req("FR-005")
def test_unparsable_page_raises_but_keeps_failed_sync_log(tmp_path):
    # Arrange
    page = tmp_path / "login.html"
    page.write_text("<html><body>Сторінка входу</body></html>", encoding="utf-8")

    # Act / Assert
    with pytest.raises(CommandError, match="^Імпорт не вдався: Таблицю розкладу САЗ не знайдено"):
        run_command(path=page)
    log = SyncLog.objects.get()
    assert log.status == SyncLog.SyncStatus.FAILED
    assert not Lesson.objects.exists()


def test_invalid_utf8_bytes_are_replaced_and_import_still_succeeds(saz_rooms, tmp_path):
    # Arrange: до збереженої сторінки дописано байт, що не є валідним UTF-8
    page = tmp_path / "broken.html"
    page.write_bytes(FIXTURE.read_bytes() + b"\n<!-- \xff -->\n")

    # Act
    lines = run_command(path=page)

    # Assert
    assert lines[:5] == COUNT_LINES
    assert lines[-1] == "Імпорт завершено"
