"""
Тести бізнес-правила SEC-003: аудит-лог бронювань є append-only.

Модуль: api.models.AuditLog і AppendOnlyQuerySet. Кожен тест має структуру AAA
(Arrange / Act / Assert), а назва тесту - речення про очікувану поведінку.

Примітка щодо використання ШІ: тести написано з допомогою ШІ (Claude) за кодом
api/models.py і вимогою SEC-003; перевірено запуском pytest і звітом покриття.
"""

from unittest.mock import Mock, patch

import pytest
from django.core.exceptions import ValidationError
from django.db import models

from api.models import AuditLog
from .conftest import at


@pytest.mark.django_db
def test_new_audit_record_with_all_fields_is_saved(make_booking, teacher, room, other_room):
    # Arrange
    booking = make_booking(at(10), at(11, 30))

    # Act
    record = AuditLog.objects.create(
        booking=booking,
        user=teacher,
        action="room_changed",
        previous_room=room,
        new_room=other_room,
        reason="Зламався проєктор",
    )

    # Assert
    saved = AuditLog.objects.get(pk=record.pk)
    assert saved.previous_room == room
    assert saved.new_room == other_room
    assert saved.created_at is not None


@pytest.mark.django_db
def test_audit_record_with_only_required_fields_is_saved(make_booking, teacher):
    # Arrange: граничний випадок - усі необовʼязкові поля порожні (скасування без зміни аудиторії)
    booking = make_booking(at(12), at(13, 30))

    # Act
    record = AuditLog.objects.create(booking=booking, user=teacher, action="booking_cancelled")

    # Assert
    saved = AuditLog.objects.get(pk=record.pk)
    assert saved.previous_room is None
    assert saved.new_room is None
    assert saved.reason == ""


@pytest.mark.django_db
def test_changing_saved_audit_record_is_forbidden_and_keeps_original_data(audit_log):
    # Arrange
    audit_log.reason = "Підроблена причина"

    # Act
    with pytest.raises(ValidationError, match="не можна змінювати"):
        audit_log.save()

    # Assert
    audit_log.refresh_from_db()
    assert audit_log.reason == "Зламався проєктор"


@pytest.mark.django_db
def test_deleting_audit_record_is_forbidden_and_keeps_record(audit_log):
    # Arrange
    record_id = audit_log.pk

    # Act
    with pytest.raises(ValidationError, match="не можна видаляти"):
        audit_log.delete()

    # Assert
    assert AuditLog.objects.filter(pk=record_id).exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("operation", "kwargs", "message"),
    [
        ("update", {"reason": "Масова зміна"}, "не можна змінювати"),
        ("delete", {}, "не можна видаляти"),
    ],
    ids=["bulk-update", "bulk-delete"],
)
def test_bulk_operation_on_audit_log_is_forbidden(audit_log, operation, kwargs, message):
    # Arrange
    queryset = AuditLog.objects.all()

    # Act
    with pytest.raises(ValidationError, match=message):
        getattr(queryset, operation)(**kwargs)

    # Assert
    audit_log.refresh_from_db()
    assert AuditLog.objects.count() == 1
    assert audit_log.reason == "Зламався проєктор"


def test_saving_existing_audit_record_is_rejected_before_reaching_database():
    # Arrange: дублер (mock) замість стану запису і замість збереження в базу - тест працює без БД
    record = AuditLog(action="room_changed")
    record._state = Mock(adding=False)

    # Act
    with patch.object(models.Model, "save") as database_save:
        with pytest.raises(ValidationError, match="не можна змінювати"):
            record.save()

    # Assert
    database_save.assert_not_called()
