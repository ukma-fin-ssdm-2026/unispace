"""
python manage.py import_saz <шлях_до_html> --semester-start 2026-09-01

Імпорт розкладу САЗ із збереженої HTML-сторінки (FR-004) з консолі, з тим самим журналом синхронізації,
що й POST /api/v1/sync/. Примітка щодо використання ШІ: команду згенеровано ШІ (Claude).
"""

from datetime import date
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from api.services.saz_import import run_sync

# Лічильники, які команда друкує (online_lessons свідомо не виводиться, як і до рефакторингу).
SUMMARY_COUNTERS = ("lessons_created", "lessons_updated", "bookings_created", "conflicts_created", "teachers_created")


class Command(BaseCommand):
    help = "Імпортує розклад із збереженої HTML-сторінки САЗ"

    def add_arguments(self, parser):
        parser.add_argument("path", help="Збережена сторінка my.ukma.edu.ua/schedule/preview/...")
        parser.add_argument("--semester-start", required=True, help="Будь-який день першого тижня, РРРР-ММ-ДД")

    def handle(self, *args, **options):
        path = _existing_file(options["path"])
        semester_start = _parse_semester_start(options["semester_start"])

        log, result = run_sync(_read_page(path), semester_start)
        if result is None:
            raise CommandError(f"Імпорт не вдався: {log.error_message}")
        self._write_summary(result.as_dict())

    def _write_summary(self, summary):
        """Друкує лічильники в сталому порядку, попередження і підсумковий рядок."""
        for key in SUMMARY_COUNTERS:
            self.stdout.write(f"{key}: {summary[key]}")
        for warning in summary["warnings"]:
            self.stdout.write(self.style.WARNING(warning))
        self.stdout.write(self.style.SUCCESS("Імпорт завершено"))


def _existing_file(raw_path):
    path = Path(raw_path)
    if not path.is_file():
        raise CommandError(f"Файл не знайдено: {path}")
    return path


def _parse_semester_start(value):
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise CommandError("--semester-start має бути датою РРРР-ММ-ДД") from error


def _read_page(path):
    """Збережена сторінка САЗ може містити невалідні байти UTF-8: їх замінюємо, а не падаємо."""
    return path.read_text(encoding="utf-8", errors="replace")
