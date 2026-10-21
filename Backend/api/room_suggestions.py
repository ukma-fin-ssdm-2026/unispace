def _is_candidate(room, min_capacity, busy_room_ids):
    return room.is_available and room.id not in busy_room_ids and room.capacity >= min_capacity


def suggest_rooms(rooms, min_capacity, busy_room_ids=(), preferred_building=None):
    candidates = [room for room in rooms if _is_candidate(room, min_capacity, busy_room_ids)]
    return sorted(candidates, key=lambda r: (r.building != preferred_building, r.capacity))
