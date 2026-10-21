from unittest.mock import Mock
from api.room_suggestions import suggest_rooms


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
