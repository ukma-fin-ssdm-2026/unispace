"""
Примітка щодо використання ШІ:
Цей модуль написано за допомогою ШІ (Claude).
ШІ використовувався для гранулярної реалізації та рефакторингу
коду відповідно до вимог TDD і виправлення помилки в межах налагодженя.
Код верифіковано людиною (Тимохина Ксенія).
"""


def _is_candidate(room, min_capacity, busy_room_ids):
    return room.is_available and room.id not in busy_room_ids and room.capacity >= min_capacity


def _rank(room, preferred_building):
    return room.building != preferred_building, room.capacity


def suggest_rooms(rooms, min_capacity, busy_room_ids=(), preferred_building=None):
    busy_room_ids = frozenset(busy_room_ids)
    candidates = [room for room in rooms if _is_candidate(room, min_capacity, busy_room_ids)]
    return sorted(candidates, key=lambda room: _rank(room, preferred_building))
