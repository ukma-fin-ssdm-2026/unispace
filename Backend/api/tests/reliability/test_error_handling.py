"""
Тест надійності: обробка помилки (Лаб 9, REL-H04).

Диспетчер завантажує через POST /api/v1/sync/ сторінку САЗ із некоректним атрибутом colspan.
Система не падає (не 500): повертає 201 зі статусом синхронізації failed і зрозумілим повідомленням,
а вже імпортовані дані лишаються без змін (REL-002). Обрана реакція - швидка відмова: хибний розклад
гірший за відсутність імпорту.

Запуск: cd Backend && python -m pytest api/tests/reliability -v

Примітка щодо використання ШІ: тест написано з допомогою ШІ (Claude) за scavenger-hunt.md (REL-H04);
запуск `pytest` локально і в CI виконує авторка PR (Ольга Михайлик).
"""

from pathlib import Path

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status

from api.models import Lesson, Room, SyncLog

pytestmark = [pytest.mark.django_db, pytest.mark.req("REL-002")]

HTML = (Path(__file__).parent.parent / "fixtures" / "saz" / "schedule_preview.html").read_text(encoding="utf-8")


def upload(client, content):
    page = SimpleUploadedFile("schedule.html", content.encode("utf-8"), content_type="text/html")
    return client.post(reverse("sync-trigger"), {"file": page, "semester_start": "2026-09-01"}, format="multipart")


def test_broken_page_returns_clear_failed_result_and_keeps_data(api_client, dispatcher):
    # Arrange: попередній імпорт успішний
    Room.objects.create(building="1", number="223", capacity=60)
    api_client.force_authenticate(user=dispatcher)
    assert upload(api_client, HTML).json()["status"] == "success"
    lessons_before = Lesson.objects.count()
    broken = HTML.replace('colspan="4"', 'colspan="1000000"', 1)

    # Act
    response = upload(api_client, broken)

    # Assert: контрольована відповідь, а не 500 чи «зависання» через роздуту таблицю
    assert response.status_code == status.HTTP_201_CREATED
    body = response.json()
    assert body["status"] == "failed"
    assert body["summary"] is None
    assert "Некоректний атрибут colspan" in body["error_message"]
    assert "invalid literal" not in body["error_message"]  # без сирого тексту винятку Python
    assert SyncLog.objects.get(pk=body["id"]).status == SyncLog.SyncStatus.FAILED
    assert Lesson.objects.count() == lessons_before
