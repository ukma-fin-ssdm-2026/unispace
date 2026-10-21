"""
TDD: перевірка перетину часових проміжків (основа пошуку вільних аудиторій, FR-010).

Тести написано за циклом Red -> Green -> Refactor; історія - у комітах з тегами [RED]/[GREEN]/[REFACTOR].
"""

from datetime import datetime, timezone

from api.services.scheduling import intervals_overlap


def t(hour, minute=0):
    return datetime(2026, 10, 20, hour, minute, tzinfo=timezone.utc)


def test_intervals_that_share_time_overlap():
    # Arrange
    first = (t(10), t(11, 30))
    second = (t(11), t(12))

    # Act
    result = intervals_overlap(*first, *second)

    # Assert
    assert result is True
