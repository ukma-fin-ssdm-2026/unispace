from datetime import datetime


def calculate_booking_duration(start_time: datetime, end_time: datetime) -> int:
    """
    Calculates the duration of a booking in minutes.
    Raises ValueError if the start time is equal to or after the end time.
    """
    if start_time >= end_time:
        raise ValueError(f"Invalid booking range: {start_time} to {end_time}")
    return int((end_time - start_time).total_seconds() / 60)
