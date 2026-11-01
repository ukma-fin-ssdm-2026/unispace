"""
python manage.py import_saz <шлях_до_html> --semester-start 2026-09-01

Імпорт розкладу САЗ із збереженої HTML-сторінки (FR-004) з консолі, з тим самим журналом синхронізації,
що й POST /api/v1/sync/. Примітка щодо використання ШІ: команду згенеровано ШІ (Claude).
"""

from datetime import date
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from api.services.saz_import import run_sync


class Command(BaseCommand):
    help = "Імпортує розклад із збереженої HTML-сторінки САЗ"

    def add_arguments(self, parser):
        parser.add_argument("path", help="Збережена сторінка my.ukma.edu.ua/schedule/preview/...")
        parser.add_argument("--semester-start", required=True, help="Будь-який день першого тижня, РРРР-ММ-ДД")

    def handle(self, *args, **options):
        path = Path(options["path"])
        if not path.is_file():
            raise CommandError(f"Файл не знайдено: {path}")
        try:
            semester_start = date.fromisoformat(options["semester_start"])
        except ValueError as error:
            raise CommandError("--semester-start має бути датою РРРР-ММ-ДД") from error

        log, result = run_sync(path.read_text(encoding="utf-8", errors="replace"), semester_start)
        if result is None:
            raise CommandError(f"Імпорт не вдався: {log.error_message}")

        summary = result.as_dict()
        for key in ("lessons_created", "lessons_updated", "bookings_created", "conflicts_created", "teachers_created"):
            self.stdout.write(f"{key}: {summary[key]}")
        for warning in summary["warnings"]:
            self.stdout.write(self.style.WARNING(warning))
        self.stdout.write(self.style.SUCCESS("Імпорт завершено"))
