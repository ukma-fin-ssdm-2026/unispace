from datetime import datetime


def calculate_booking_duration(start_time: datetime, end_time: datetime) -> int:
    if start_time > end_time:
        raise ValueError("Start time cannot be after end time")
    return int((end_time - start_time).total_seconds() / 60)
