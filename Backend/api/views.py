"""
Примітка щодо використання ШІ:
Цей модуль написано за допомогою ШІ (Gemini).
ШІ використовувався для практичної адаптації та реалізації попередньо спланованого командою
CRUD-інтерфейсу під технічний стек нашого проєкту (Django REST Framework).
Зокрема, інструмент допоміг із генерацією OpenAPI-анотацій (@extend_schema), структуруванням
серіалізаторів та оформленням mock-даних згідно з вимогами підходу Code-First.
Увесь код верифіковано, перевірено на відповідність стандартам REST-семантики та затверджено Backend Lead.
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, BasePermission
from drf_spectacular.utils import extend_schema

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
)


class IsTeacherOrDispatcher(BasePermission):
    """
    Кастомний дозвіл (SEC-001/NFR-4):
    Тільки викладачі та диспетчери можуть створювати або видаляти бронювання.
    """

    def has_permission(self, request, view):
        # Реальна логіка на майбутнє:
        # return bool(
        #     request.user and
        #     request.user.is_authenticated and
        #     getattr(request.user, 'role', 'student') in ['teacher', 'dispatcher']
        # )

        # Заглушка для Лабораторної 4, щоб Swagger-демо працювало без токенів:
        return True  # Для показу заборони використайте False


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
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Отримати список аудиторій (оновлено)",
        parameters=[RoomQuerySerializer],
        responses={200: RoomSerializer(many=True), 400: ErrorResponseSerializer},
    )
    def get(self, request, format=None):
        query = RoomQuerySerializer(data=request.query_params)
        if not query.is_valid():
            return Response(get_validation_error_response(query.errors), status=status.HTTP_400_BAD_REQUEST)

        # Заглушка
        mock_data = [
            {"id": 1, "name": "Space A", "capacity": 20, "has_projector": True},
            {"id": 2, "name": "Space B", "capacity": 50, "has_projector": False},
        ]
        return Response(RoomSerializer(mock_data, many=True).data, status=status.HTTP_200_OK)


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

        response_data = serializer.validated_data
        response_data["id"] = 101
        response_data["status"] = "booked"
        return Response(response_data, status=status.HTTP_201_CREATED)


class BookingDetailAPIView(APIView):
    permission_classes = [IsTeacherOrDispatcher]

    @extend_schema(
        summary="Скасувати бронювання",
        responses={204: None, 403: ErrorResponseSerializer, 404: ErrorResponseSerializer},
    )
    def delete(self, request, pk, format=None):
        # Виконано вимогу: 404 для неіснуючого (або від'ємного) ID
        if pk <= 0:
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
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Бронювання поточного користувача",
        parameters=[UserBookingsQuerySerializer],
        responses={200: BookingResponseSerializer(many=True), 400: ErrorResponseSerializer},
    )
    def get(self, request, format=None):
        query = UserBookingsQuerySerializer(data=request.query_params)
        if not query.is_valid():
            return Response(get_validation_error_response(query.errors), status=status.HTTP_400_BAD_REQUEST)

        mock_data = [
            {
                "id": 101,
                "room_id": 1,
                "start_time": "2026-10-02T10:00:00Z",
                "end_time": "2026-10-02T11:30:00Z",
                "title": "Зустріч SpaceOps",
                "status": "active",
            }
        ]
        return Response(mock_data, status=status.HTTP_200_OK)


class SyncLogListAPIView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Отримати історію синхронізацій",
        description="Повертає список логів імпорту розкладу із САЗ.",
        responses={200: SyncLogSerializer(many=True)},
    )
    def get(self, request, format=None):
        # Заглушка (Mock-дані)
        mock_logs = [
            {
                "id": 1,
                "started_at": "2026-10-15T08:00:00Z",
                "finished_at": "2026-10-15T08:05:00Z",
                "status": "success",
                "trigger": "scheduled",
                "error_message": None,
            },
            {
                "id": 2,
                "started_at": "2026-10-15T09:10:00Z",
                "finished_at": "2026-10-15T09:10:30Z",
                "status": "failed",
                "trigger": "manual",
                "error_message": "Timeout 30s",
            },
        ]
        serializer = SyncLogSerializer(mock_logs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class SyncTriggerAPIView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Запустити імпорт розкладу",
        description=(
            "Ручний запуск синхронізації. У разі спрацьовування " "Circuit Breaker повертає 429 Too Many Requests."
        ),
        request=None,
        responses={201: SyncLogSerializer, 429: ErrorResponseSerializer},
    )
    def post(self, request, format=None):
        # Заглушка для успішного старту (створення запису in_progress)
        mock_response = {
            "id": 3,
            "started_at": "2026-10-15T09:27:00Z",
            "finished_at": None,
            "status": "in_progress",
            "trigger": "manual",
            "error_message": None,
        }
        serializer = SyncLogSerializer(mock_response)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
