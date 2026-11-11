"""
Перевірки надійності валідації часу САЗ (Lab09, REL-H05).

Примітка щодо використання ШІ: ШІ допоміг підготувати перевірку часу
та тестові сценарії.
"""

from datetime import time
from pathlib import Path

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status

from api.models import Booking, Lesson, Room, SyncLog
from api.services.saz_parser import SazParseError, parse_schedule

pytestmark = [
    pytest.mark.req("FR-004"),
    pytest.mark.req("REL-002"),
]

HTML = (Path(__file__).parent.parent / "fixtures" / "saz" / "schedule_preview.html").read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "slot",
    [
        "25:99-26:99",
        "24:00-24:30",
        "8:60-9:50",
        "8:30-24:00",
        "9:50-8:30",
        "8:30-8:30",
    ],
)
def test_invalid_time_rejects_page_with_clear_error(slot):
    # Arrange
    broken = HTML.replace("8:30-9:50", slot, 1)
    assert broken != HTML

    # Act / Assert
    with pytest.raises(SazParseError, match="Некоректний час заняття"):
        parse_schedule(broken)


@pytest.mark.parametrize(
    "slot,expected_start,expected_end",
    [
        ("00:00-00:01", time(0, 0), time(0, 1)),
        ("23:58-23:59", time(23, 58), time(23, 59)),
        ("8:30-9:50", time(8, 30), time(9, 50)),
    ],
)
def test_valid_time_boundaries_are_accepted(slot, expected_start, expected_end):
    # Arrange
    html = HTML.replace("8:30-9:50", slot, 1)

    # Act
    result = parse_schedule(html)

    # Assert
    first = result.entries[0]
    assert (first.start, first.end) == (expected_start, expected_end)


def test_unrecognized_time_keeps_existing_warning_behavior():
    # Arrange
    html = HTML.replace("8:30-9:50", "час уточнюється", 1)

    # Act
    result = parse_schedule(html)

    # Assert
    assert len(result.entries) == 5
    assert any("не розпізнано день або час" in warning for warning in result.warnings)


@pytest.mark.django_db
def test_invalid_time_returns_failed_sync_and_keeps_previous_data(api_client, dispatcher):
    # Arrange
    Room.objects.create(building="1", number="223", capacity=60)
    api_client.force_authenticate(user=dispatcher)

    def upload(content):
        page = SimpleUploadedFile(
            "schedule.html",
            content.encode("utf-8"),
            content_type="text/html",
        )
        return api_client.post(
            reverse("sync-trigger"),
            {"file": page, "semester_start": "2026-09-01"},
            format="multipart",
        )

    successful = upload(HTML)
    assert successful.status_code == status.HTTP_201_CREATED
    assert successful.json()["status"] == "success"

    lessons_before = list(Lesson.objects.order_by("pk").values())
    bookings_before = list(Booking.objects.order_by("pk").values())
    assert lessons_before

    broken = HTML.replace("8:30-9:50", "25:99-26:99", 1)
    assert broken != HTML

    # Act
    response = upload(broken)

    # Assert
    assert response.status_code == status.HTTP_201_CREATED
    body = response.json()
    assert body["status"] == "failed"
    assert body["summary"] is None
    assert "Некоректний час заняття" in body["error_message"]
    assert "hour must be" not in body["error_message"]

    log = SyncLog.objects.get(pk=body["id"])
    assert log.status == SyncLog.SyncStatus.FAILED
    assert log.finished_at is not None

    assert list(Lesson.objects.order_by("pk").values()) == lessons_before
    assert list(Booking.objects.order_by("pk").values()) == bookings_before
