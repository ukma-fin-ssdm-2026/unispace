from datetime import datetime


def calculate_booking_duration(start_time: datetime, end_time: datetime) -> int:
    return int((end_time - start_time).total_seconds() / 60)
