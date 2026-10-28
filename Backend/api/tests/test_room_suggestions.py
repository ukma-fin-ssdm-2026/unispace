"""
Примітка щодо використання ШІ:
Цей модуль написано за допомогою ШІ (Claude).
ШІ використовувався для реалізації тестів відповідно до вимог TDD
і пошуку та виправлення помилки в межах налагодженя.
Код верифіковано людиною (Тимохина Ксенія).
"""

import pytest
from unittest.mock import Mock
from api.room_suggestions import suggest_rooms

pytestmark = pytest.mark.req("US-10")


def make_room(room_id, capacity, building="1", is_available=True):
    return Mock(
        id=room_id,
        capacity=capacity,
        building=building,
        is_available=is_available,
    )


def test_rooms_smaller_than_required_capacity_are_not_suggested():
    small, enough = make_room(1, capacity=20), make_room(2, capacity=30)
    result = suggest_rooms([small, enough], min_capacity=30)
    assert result == [enough]


def test_busy_rooms_are_not_suggested():
    busy = make_room(1, capacity=30)
    free = make_room(2, capacity=30)
    result = suggest_rooms([busy, free], min_capacity=10, busy_room_ids={busy.id})
    assert result == [free]


def test_rooms_marked_unavailable_are_not_suggested():
    closed = make_room(1, capacity=30, is_available=False)
    open_room = make_room(2, capacity=30)
    result = suggest_rooms([closed, open_room], min_capacity=10)
    assert result == [open_room]


def test_rooms_are_sorted_from_smallest_sufficient_capacity():
    huge, snug, medium = make_room(1, capacity=100), make_room(2, capacity=30), make_room(3, capacity=50)
    result = suggest_rooms([huge, snug, medium], min_capacity=30)
    assert result == [snug, medium, huge]


def test_rooms_from_preferred_building_come_first():
    far_small = make_room(1, capacity=30, building="2")
    near_big = make_room(2, capacity=60, building="1")
    result = suggest_rooms([far_small, near_big], min_capacity=30, preferred_building="1")
    assert result == [near_big, far_small]


def test_busy_rooms_given_as_generator_are_all_excluded():
    rooms = [make_room(room_id, capacity=30) for room_id in range(1, 5)]
    busy_ids = (room.id for room in rooms[1:3])
    result = suggest_rooms(rooms, min_capacity=10, busy_room_ids=busy_ids)
    assert result == [rooms[0], rooms[3]]
