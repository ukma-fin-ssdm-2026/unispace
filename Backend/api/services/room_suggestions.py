"""
Алгоритм підбору альтернативних аудиторій для перенесення занять.
Цей модуль містить логіку фільтрації та ранжування вільних кімнат.

Примітка щодо використання ШІ: цей модуль написано за допомогою ШІ (Claude).
ШІ використовувався для гранулярної реалізації та рефакторингу коду
відповідно до вимог TDD і виправлення помилки в межах налагодження.
Код верифіковано людиною (Тимохина Ксенія).
"""

# ==========================================
# Допоміжні функції (фільтрація та ранжування)
# ==========================================


def _is_candidate(room, min_capacity, busy_room_ids):
    return room.is_available and room.id not in busy_room_ids and room.capacity >= min_capacity


def _rank(room, preferred_building):
    return room.building != preferred_building, room.capacity

    # ==========================================
    # Основний алгоритм підбору
    # ==========================================


def suggest_rooms(rooms, min_capacity, busy_room_ids=(), preferred_building=None):
    busy_room_ids = frozenset(busy_room_ids)
    candidates = [room for room in rooms if _is_candidate(room, min_capacity, busy_room_ids)]
    return sorted(candidates, key=lambda room: _rank(room, preferred_building))
