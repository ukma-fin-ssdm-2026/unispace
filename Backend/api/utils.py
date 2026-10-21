def can_room_accommodate(room_capacity: int, attendees_count: int) -> bool:
    """Check if a room has enough capacity for attendees.

    Raises ValueError if the attendees count is not positive.
    """
    if attendees_count <= 0:
        raise ValueError("Attendees count must be greater than zero")

    return attendees_count <= room_capacity