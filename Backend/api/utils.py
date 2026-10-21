from datetime import datetime


def calculate_booking_duration(start_time: datetime, end_time: datetime) -> int:
    if start_time > end_time:
        raise ValueError(f"Invalid booking range: {start_time} to {end_time}")
    return int((end_time - start_time).total_seconds() / 60)
