
from unittest.mock import Mock

import pytest
from rest_framework.test import APIRequestFactory

from api.serializers import RoomQuerySerializer, SyncLogSerializer
from api.views import IsDispatcher, get_validation_error_response

from unittest.mock import patch
from rest_framework.test import APIRequestFactory

from api.views import RoomListAPIView


@pytest.fixture
def dispatcher_request():
    """Запит із підставним користувачем-диспетчером."""
    request = APIRequestFactory().get("/api/v1/sync-logs/")
    request.user = Mock(is_authenticated=True, role="dispatcher")
    return request


@pytest.mark.parametrize("limit,valid", [
    (1, True),
    (20, True),
    (0, False),
    (-1, False),
])
def test_room_limit_boundaries(limit, valid):
    # Arrange
    serializer = RoomQuerySerializer(data={"limit": limit})

    # Act
    result = serializer.is_valid()

    # Assert
    assert result is valid


@pytest.mark.parametrize("capacity,valid", [
    (1, True),
    (30, True),
    (0, False),
    (-1, False),
])
def test_room_capacity_boundaries(capacity, valid):
    # Arrange
    serializer = RoomQuerySerializer(data={"capacity": capacity})

    # Act
    result = serializer.is_valid()

    # Assert
    assert result is valid


@pytest.mark.parametrize("status,valid", [
    ("in_progress", True),
    ("success", True),
    ("failed", True),
    ("unknown", False),
])
def test_sync_status_choices(status, valid):
    # Arrange
    serializer = SyncLogSerializer(data={
        "started_at": "2026-10-20T10:00:00Z",
        "status": status,
        "trigger": "manual",
    })

    # Act
    result = serializer.is_valid()

    # Assert
    assert result is valid


def test_dispatcher_can_access_sync_logs(dispatcher_request):
    # Arrange
    permission = IsDispatcher()

    # Act
    result = permission.has_permission(dispatcher_request, None)

    # Assert
    assert result is True


@pytest.mark.parametrize("role", ["student", "teacher", None])
def test_other_roles_cannot_access_sync_logs(role):
    # Arrange
    request = Mock()
    request.user = Mock(is_authenticated=True, role=role)
    permission = IsDispatcher()

    # Act
    result = permission.has_permission(request, None)

    # Assert
    assert result is False


def test_validation_error_response_contains_field_name():
    # Arrange
    errors = {"limit": ["Має бути більше нуля."]}

    # Act
    result = get_validation_error_response(errors)

    # Assert
    assert result["error"]["details"][0]["field"] == "limit"


def test_room_list_uses_room_manager():
    # Arrange
    request = APIRequestFactory().get("/api/v1/rooms/")

    with patch("api.views.Room.objects.all") as mock_all:
        mock_all.return_value = []

        # Act
        response = RoomListAPIView.as_view()(request)

        # Assert
        assert response.status_code == 200
        mock_all.assert_called_once_with()


def test_unauthenticated_user_cannot_access_sync_logs():
    # Arrange
    request = Mock()
    request.user = Mock(is_authenticated=False, role="dispatcher")
    permission = IsDispatcher()

    # Act
    result = permission.has_permission(request, None)

    # Assert
    assert result is False
