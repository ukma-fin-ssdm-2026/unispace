from datetime import datetime
from api.utils import calculate_booking_duration


def test_calculate_duration_basic():
    start = datetime(2026, 10, 10, 10, 0)
    end = datetime(2026, 10, 10, 11, 30)
    assert calculate_booking_duration(start, end) == 90
