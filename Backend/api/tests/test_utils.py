from datetime import datetime
from api.utils import calculate_booking_duration
import pytest


def test_calculate_duration_basic():
    start = datetime(2026, 10, 10, 10, 0)
    end = datetime(2026, 10, 10, 11, 30)
    assert calculate_booking_duration(start, end) == 90


def test_calculate_duration_start_after_end():
    start = datetime(2026, 10, 10, 12, 0)
    end = datetime(2026, 10, 10, 10, 0)
    with pytest.raises(ValueError):
        calculate_booking_duration(start, end)


def test_calculate_duration_zero_minutes():
    start = datetime(2026, 10, 10, 10, 0)
    with pytest.raises(ValueError):
        calculate_booking_duration(start, start)
