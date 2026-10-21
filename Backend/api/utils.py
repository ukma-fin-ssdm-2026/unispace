def can_room_accommodate(room_capacity: int, attendees_count: int) -> bool:
    """Check whether a room can accommodate the requested attendees."""
    if attendees_count <= 0:
        raise ValueError("Attendees count must be greater than zero")

    return attendees_count <= room_capacity