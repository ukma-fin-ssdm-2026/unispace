def suggest_rooms(rooms, min_capacity, busy_room_ids=(), preferred_building=None):
    result = []
    for room in rooms:
        if room.capacity >= min_capacity:
            result.append(room)
    return result
