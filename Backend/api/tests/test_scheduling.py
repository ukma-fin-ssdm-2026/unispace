"""
TDD: перевірка перетину часових проміжків (основа пошуку вільних аудиторій, FR-010).

Тести написано за циклом Red -> Green -> Refactor; історія - у комітах з тегами [RED]/[GREEN]/[REFACTOR].
"""

from datetime import datetime, timedelta, timezone

import pytest

from api.services.scheduling import intervals_overlap, overlap_duration


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


def test_intervals_that_only_touch_do_not_overlap():
    # Arrange: граничний випадок - перша пара закінчується рівно тоді, коли починається друга
    first = (t(10), t(11))
    second = (t(11), t(12))

    # Act
    result = intervals_overlap(*first, *second)

    # Assert
    assert result is False


def test_time_without_timezone_is_rejected():
    # Arrange: час без часового поясу - незрозуміло, це Київ чи UTC (різниця 2-3 години)
    naive_start = datetime(2026, 10, 20, 10, 0)
    naive_end = datetime(2026, 10, 20, 11, 0)
    aware_interval = (t(10, 30), t(12))

    # Act / Assert
    with pytest.raises(ValueError, match="часовим поясом"):
        intervals_overlap(naive_start, naive_end, *aware_interval)


def test_overlap_duration_is_length_of_shared_time():
    # Arrange: перша пара 10:00-11:30, друга 11:00-12:00, спільні 30 хвилин
    first = (t(10), t(11, 30))
    second = (t(11), t(12))

    # Act
    result = overlap_duration(*first, *second)

    # Assert
    assert result == timedelta(minutes=30)
