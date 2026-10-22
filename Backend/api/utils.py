from datetime import datetime


def calculate_booking_duration(start_time: datetime, end_time: datetime) -> int:
    """
    Calculates the duration of a booking in minutes.
    Raises ValueError if the start time is equal to or after the end time.
    """
    if start_time >= end_time:
        raise ValueError(f"Invalid booking range: {start_time} to {end_time}")
    return int((end_time - start_time).total_seconds() / 60)


def can_room_accommodate(room_capacity: int, attendees_count: int) -> bool:
    """Check if a room has enough capacity for attendees.

    Raises ValueError if the attendees count is not positive.
    """
    if attendees_count <= 0:
        raise ValueError("Attendees count must be greater than zero")

    return attendees_count <= room_capacity