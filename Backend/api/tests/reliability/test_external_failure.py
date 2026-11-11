"""
Тест надійності: зовнішня відмова, ін'єкція збою (Лаб 9, REL-H07).

Тестовий дублер (unittest.mock.patch) імітує обрив з'єднання з PostgreSQL (OperationalError)
посеред імпорту розкладу через POST /api/v1/sync/. Обрана на Етапі 3 реакція - швидка відмова:
- клієнт отримує 500 без внутрішніх деталей (тексту винятку, SQL);
- журнал синхронізації не «зависає» в in_progress, а закривається як failed із загальним повідомленням;
- деталі збою потрапляють у лог сервера;
- раніше імпортовані дані не змінюються (REL-002).

Запуск: cd Backend && python -m pytest api/tests/reliability -v

Примітка щодо використання ШІ: тест написано з допомогою ШІ (Claude) за scavenger-hunt.md (REL-H07);
запуск `pytest` локально і в CI виконує авторка PR (Ольга Михайлик).
"""

from pathlib import Path
from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import OperationalError
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from api.models import Lesson, SyncLog

pytestmark = [pytest.mark.django_db, pytest.mark.req("REL-002")]

INTERNAL_DETAIL = "connection to server at 10.0.0.5 lost"
PAGE = (Path(__file__).parent.parent / "fixtures" / "saz" / "schedule_preview.html").read_bytes()


def test_database_outage_during_import_fails_fast_and_closes_sync_log(dispatcher, caplog):
    # Arrange: клієнт повертає 500 як справжній браузер, а не прокидає виняток у тест
    client = APIClient(raise_request_exception=False)
    client.force_authenticate(user=dispatcher)
    # Сторінка коректна, тож парсер її розбирає і збій стається саме на записі в базу
    page = SimpleUploadedFile("schedule.html", PAGE, content_type="text/html")

    # Act: база «падає» посеред імпорту
    with patch("api.services.saz_import.import_schedule", side_effect=OperationalError(INTERNAL_DETAIL)):
        response = client.post(
            reverse("sync-trigger"), {"file": page, "semester_start": "2026-09-01"}, format="multipart"
        )

    # Assert: швидка відмова без витоку деталей
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert INTERNAL_DETAIL not in response.content.decode("utf-8", errors="replace")

    # Assert: журнал закрито чесно, деталі - лише в лозі сервера
    log = SyncLog.objects.get()
    assert log.status == SyncLog.SyncStatus.FAILED
    assert log.finished_at is not None
    assert log.error_message == "Неочікувана помилка імпорту: OperationalError"
    assert INTERNAL_DETAIL in caplog.text
    assert not Lesson.objects.exists()
