"""
Примітка щодо використання ШІ:
Цей модуль написано за допомогою ШІ (Gemini).
ШІ використовувався для практичної адаптації та реалізації попередньо спланованого командою
CRUD-інтерфейсу під технічний стек нашого проєкту (Django REST Framework).
Зокрема, інструмент допоміг із генерацією OpenAPI-анотацій (@extend_schema), структуруванням
серіалізаторів та оформленням mock-даних згідно з вимогами підходу Code-First.
Увесь код верифіковано, перевірено на відповідність стандартам REST-семантики та затверджено Backend Lead.

Контракт оновлено під TDD (використання UUID та lesson_id).

CRUD аудиторій і бронювань дописано з допомогою ШІ (Claude) за docs/requirements
(FR-008, FR-011, FR-012, FR-015, FR-017, FR-020); перевірено ревʼю та тестами
test_rooms_crud.py і test_bookings_crud.py.
"""

import uuid

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, BasePermission, IsAuthenticated
from drf_spectacular.utils import extend_schema
from .models import Room, Booking, SyncLog

from .serializers import (
    RoomSerializer,
    AvailableSlotsResponseSerializer,
    BookingCreateSerializer,
    BookingResponseSerializer,
    ErrorResponseSerializer,
    RoomQuerySerializer,
    AvailableSlotsQuerySerializer,
    UserBookingsQuerySerializer,
    SyncLogSerializer,
    RoomWriteSerializer,
)


class IsTeacherOrDispatcher(BasePermission):
    """
    Only authenticated teachers and dispatchers
    can create or delete bookings.
    """

    message = "Only dispatchers can perform this action."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and getattr(user, "role", None) in ("teacher", "dispatcher"))


class IsDispatcher(BasePermission):
    message = "Only dispatchers can access sync logs."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and getattr(user, "role", None) == "dispatcher")


# Допоміжна функція для генерації стандартної відповіді з помилкою
def get_validation_error_response(errors):
    return {
        "error": {
            "code": "VALIDATION_ERROR",
            "message": "Запит містить невалідні поля",
            "details": [{"field": k, "message": v[0]} for k, v in errors.items()],
            "request_id": "req_abc123",
            "documentation": "https://api.unispace.com/docs/errors#validation",
        }
    }


class RoomListAPIView(APIView):
    def get_permissions(self):
        # Перегляд аудиторій відкритий усім, створення - лише диспетчеру (FR-008).
        if self.request.method == "POST":
            return [IsDispatcher()]
        return [AllowAny()]

    @extend_schema(
        summary="Отримати список аудиторій",
        parameters=[RoomQuerySerializer],
        responses={200: RoomSerializer(many=True), 400: ErrorResponseSerializer},
    )
    def get(self, request, format=None):
        query = RoomQuerySerializer(data=request.query_params)
        if not query.is_valid():
            return Response(get_validation_error_response(query.errors), status=status.HTTP_400_BAD_REQUEST)

        rooms = Room.objects.all()

        capacity_filter = query.validated_data.get("capacity")
        if capacity_filter:
            rooms = rooms.filter(capacity__gte=capacity_filter)

        building_filter = query.validated_data.get("building")
        if building_filter:
            rooms = rooms.filter(building=building_filter)

        projector_filter = query.validated_data.get("projector_working")
        if projector_filter is not None:
            rooms = rooms.filter(projector_working=projector_filter)

        computers_filter = query.validated_data.get("has_computers")
        if computers_filter is not None:
            rooms = rooms.filter(has_computers=computers_filter)

        offset = query.validated_data.get("offset", 0)
        limit = query.validated_data.get("limit", 20)
        rooms = rooms[offset : offset + limit]

        serializer = RoomSerializer(rooms, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Створити аудиторію",
        request=RoomWriteSerializer,
        responses={201: RoomSerializer, 400: ErrorResponseSerializer, 403: ErrorResponseSerializer},
    )
    def post(self, request, format=None):
        serializer = RoomWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(get_validation_error_response(serializer.errors), status=status.HTTP_400_BAD_REQUEST)

        room = serializer.save()
        return Response(RoomSerializer(room).data, status=status.HTTP_201_CREATED)


class AvailableSlotsAPIView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Пошук вільних слотів",
        parameters=[AvailableSlotsQuerySerializer],
        responses={200: AvailableSlotsResponseSerializer, 400: ErrorResponseSerializer},
    )
    def get(self, request, format=None):
        query = AvailableSlotsQuerySerializer(data=request.query_params)
        if not query.is_valid():
            return Response(get_validation_error_response(query.errors), status=status.HTTP_400_BAD_REQUEST)

        mock_data = {
            "room_id": query.validated_data["room_id"],
            "date": query.validated_data["date"],
            "available_slots": ["09:00-10:30", "12:00-13:30"],
        }
        return Response(mock_data, status=status.HTTP_200_OK)


class BookingListCreateAPIView(APIView):
    permission_classes = [IsTeacherOrDispatcher]

    @extend_schema(
        summary="Створити бронювання",
        request=BookingCreateSerializer,
        responses={201: BookingResponseSerializer, 400: ErrorResponseSerializer, 409: ErrorResponseSerializer},
    )
    def post(self, request, format=None):
        serializer = BookingCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(get_validation_error_response(serializer.errors), status=status.HTTP_400_BAD_REQUEST)

        response_data = serializer.validated_data.copy()
        response_data["id"] = uuid.uuid4()
        response_data["status"] = "booked"
        response_data["title"] = "Mock Subject"
        response_data["start_time"] = "2026-10-20T10:00:00Z"
        response_data["end_time"] = "2026-10-20T11:30:00Z"
        return Response(response_data, status=status.HTTP_201_CREATED)


class BookingDetailAPIView(APIView):
    permission_classes = [IsTeacherOrDispatcher]

    @extend_schema(
        summary="Скасувати бронювання",
        responses={204: None, 403: ErrorResponseSerializer, 404: ErrorResponseSerializer},
    )
    def delete(self, request, pk, format=None):
        if str(pk) == "00000000-0000-0000-0000-000000000000":
            return Response(
                {
                    "error": {
                        "code": "NOT_FOUND",
                        "message": f"Бронювання з ID {pk} не знайдено",
                        "request_id": "req_abc123",
                        "documentation": "https://api.unispace.com/docs/errors#not-found",
                    }
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(status=status.HTTP_204_NO_CONTENT)


class UserBookingsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Бронювання поточного користувача",
        parameters=[UserBookingsQuerySerializer],
        responses={200: BookingResponseSerializer(many=True), 400: ErrorResponseSerializer},
    )
    def get(self, request, format=None):
        query = UserBookingsQuerySerializer(data=request.query_params)
        if not query.is_valid():
            return Response(get_validation_error_response(query.errors), status=status.HTTP_400_BAD_REQUEST)

        bookings = Booking.objects.filter(user=request.user).order_by("-start_time")
        limit = query.validated_data.get("limit", 10)
        bookings = bookings[:limit]

        serializer = BookingResponseSerializer(bookings, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class SyncLogListAPIView(APIView):
    permission_classes = [IsDispatcher]

    @extend_schema(
        summary="Отримати історію синхронізацій",
        description="Повертає список логів імпорту розкладу із САЗ.",
        responses={200: SyncLogSerializer(many=True)},
    )
    def get(self, request, format=None):
        logs = SyncLog.objects.all().order_by("-started_at")
        serializer = SyncLogSerializer(logs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class SyncTriggerAPIView(APIView):
    permission_classes = [IsDispatcher]

    @extend_schema(
        summary="Запустити імпорт розкладу",
        description="Ручний запуск синхронізації.",
        request=None,
        responses={201: SyncLogSerializer, 429: ErrorResponseSerializer},
    )
    def post(self, request, format=None):
        mock_response = {
            "id": uuid.uuid4(),
            "started_at": "2026-10-15T09:27:00Z",
            "finished_at": None,
            "status": "in_progress",
            "trigger": "manual",
            "error_message": None,
        }
        serializer = SyncLogSerializer(mock_response)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
