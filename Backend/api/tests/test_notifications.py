"""
Модульні тести для сервісу сповіщень (FR-015).
TP-01: Перевірка генерації Email-шаблону.

Примітка щодо використання ШІ: тести згенеровано ШІ як специфікацію
генерації шаблону листа з використанням дублерів (Mock).
Верифіковано локальним запуском pytest.
"""

from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from api.services.notifications import generate_room_change_email_body

pytestmark = pytest.mark.req("US-07", "FR-015")

# ==========================================
# Тести генерації сповіщень
# ==========================================


def test_generate_room_change_email_body_contains_all_required_fields():
    # Arrange: створюємо моки, додаємо імітацію викладача
    teacher_mock = Mock(full_name="Тестовий Викладач")
    lesson_mock = Mock(subject="Програмна інженерія", teacher=teacher_mock)

    booking_mock = Mock(lesson=lesson_mock, start_time=datetime(2026, 10, 21, 10, 0, tzinfo=timezone.utc))

    previous_room_mock = Mock(number="1-225")
    new_room_mock = Mock(id="123e4567-e89b-12d3-a456-426614174000", number="1-226")

    # Act
    email_body = generate_room_change_email_body(
        booking=booking_mock, previous_room=previous_room_mock, new_room=new_room_mock
    )

    # Assert: перевіряємо наявність усіх елементів згідно з FR-015 та TP-01
    assert "Програмна інженерія" in email_body
    assert "Тестовий Викладач" in email_body
    assert "21.10.2026 10:00" in email_body
    assert "1-225" in email_body
    assert "1-226" in email_body

    # Перевіряємо, що room_id дійсно підставився у посилання
    assert "123e4567-e89b-12d3-a456-426614174000" in email_body
