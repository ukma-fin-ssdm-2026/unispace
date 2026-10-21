def can_room_accommodate(room_capacity: int, attendees_count: int) -> bool:
    """Check whether a room can accommodate the requested attendees."""
    return attendees_count <= room_capacity