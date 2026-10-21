def _is_candidate(room, min_capacity, busy_room_ids):
    """Аудиторія підходить, якщо вона доступна, вільна й має достатню місткість."""
    return room.is_available and room.id not in busy_room_ids and room.capacity >= min_capacity


def suggest_rooms(rooms, min_capacity, busy_room_ids=(), preferred_building=None):
    return [room for room in rooms if _is_candidate(room, min_capacity, busy_room_ids)]

