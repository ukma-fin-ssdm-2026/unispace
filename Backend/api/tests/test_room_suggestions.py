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
