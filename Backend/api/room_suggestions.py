def suggest_rooms(rooms, min_capacity, busy_room_ids=(), preferred_building=None):
    return [room for room in rooms if room.capacity >= min_capacity]
