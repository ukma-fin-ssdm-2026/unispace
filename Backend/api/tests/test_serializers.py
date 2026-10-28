"""
Тести валідації та граничних значень серіалізаторів.

Примітка щодо використання ШІ: модуль згенеровано за допомогою ШІ (Claude)
для перевірки валідації полів та граничних значень; перевірено локальним запуском pytest.
"""

import pytest
from api.serializers import RoomQuerySerializer, SyncLogSerializer


@pytest.mark.req("USAB-001")
@pytest.mark.parametrize(
    "limit,valid",
    [
        (1, True),
        (20, True),
        (0, False),
        (-1, False),
    ],
)
def test_room_limit_boundaries(limit, valid):
    # Arrange
    serializer = RoomQuerySerializer(data={"limit": limit})

    # Act
    result = serializer.is_valid()

    # Assert
    assert result is valid


@pytest.mark.req("USAB-001")
@pytest.mark.parametrize(
    "capacity,valid",
    [
        (1, True),
        (30, True),
        (0, False),
        (-1, False),
    ],
)
def test_room_capacity_boundaries(capacity, valid):
    # Arrange
    serializer = RoomQuerySerializer(data={"capacity": capacity})

    # Act
    result = serializer.is_valid()

    # Assert
    assert result is valid


@pytest.mark.parametrize(
    "status,valid",
    [
        ("in_progress", True),
        ("success", True),
        ("failed", True),
        ("unknown", False),
    ],
)
def test_sync_status_choices(status, valid):
    # Arrange
    serializer = SyncLogSerializer(
        data={
            "started_at": "2026-10-20T10:00:00Z",
            "status": status,
            "trigger": "manual",
        }
    )

    # Act
    result = serializer.is_valid()

    # Assert
    assert result is valid
