"""
Примітка щодо використання ШІ:
Цей модуль написано за допомогою ШІ (Gemini).
ШІ використовувався для практичної адаптації та реалізації попередньо спланованого командою CRUD-інтерфейсу під технічний стек нашого проєкту (Django REST Framework).
Зокрема, інструмент допоміг із генерацією OpenAPI-анотацій (@extend_schema), структуруванням серіалізаторів та оформленням mock-даних згідно з вимогами підходу Code-First.
Увесь код верифіковано, перевірено на відповідність стандартам REST-семантики та затверджено Backend Lead.
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, BasePermission
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

from .serializers import (
    RoomSerializer, AvailableSlotsResponseSerializer,
    BookingCreateSerializer, BookingResponseSerializer, ErrorResponseSerializer
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
        return True # Для показу заборони використайте False

class RoomListAPIView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Отримати список аудиторій",
        description="Повертає перелік аудиторій. Використовується пагінація на основі зсуву (limit/offset).",
        parameters=[
            OpenApiParameter(name='limit', description='Кількість записів', required=False, type=int, default=20),
            OpenApiParameter(name='offset', description='Зсув', required=False, type=int, default=0),
            OpenApiParameter(name='capacity', description='Мінімальна місткість', required=False, type=int),
        ],
        responses={200: RoomSerializer(many=True)}
    )
    def get(self, request, format=None):
        # Заглушка. В майбутньому: rooms = Room.objects.all() ...
        mock_data = [
            {"id": 1, "name": "Space A", "capacity": 20, "has_projector": True},
            {"id": 2, "name": "Space B", "capacity": 50, "has_projector": False},
        ]
        serializer = RoomSerializer(mock_data, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class AvailableSlotsAPIView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Пошук вільних слотів",
        parameters=[
            OpenApiParameter(name='room_id', required=True, type=int),
            OpenApiParameter(name='date', required=True, type=OpenApiTypes.DATE),
        ],
        responses={200: AvailableSlotsResponseSerializer, 400: ErrorResponseSerializer}
    )
    def get(self, request, format=None):
        mock_data = {
            "room_id": int(request.GET.get('room_id', 1)),
            "date": request.GET.get('date', "2026-10-02"),
            "available_slots": ["09:00-10:30", "12:00-13:30"]
        }
        return Response(mock_data, status=status.HTTP_200_OK)


class BookingListCreateAPIView(APIView):
    permission_classes = [IsTeacherOrDispatcher]

    @extend_schema(
        summary="Створити бронювання",
        request=BookingCreateSerializer,
        responses={
            201: BookingResponseSerializer,
            400: ErrorResponseSerializer,
            409: ErrorResponseSerializer
        }
    )
    def post(self, request, format=None):
        serializer = BookingCreateSerializer(data=request.data)

        # Демонстрація валідації та узгодженої структури помилок
        if not serializer.is_valid():
            error_response = {
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Запит містить невалідні поля",
                    "details": [{"field": k, "message": v[0]} for k, v in serializer.errors.items()],
                    "request_id": "req_abc123",
                    "documentation": "https://api.unispace.com/docs/errors#validation"
                }
            }
            return Response(error_response, status=status.HTTP_400_BAD_REQUEST)

        # Заглушка успішного створення. В майбутньому: serializer.save()
        response_data = serializer.validated_data
        response_data['id'] = 101
        response_data['status'] = "booked"
        return Response(response_data, status=status.HTTP_201_CREATED)


class BookingDetailAPIView(APIView):
    permission_classes = [IsTeacherOrDispatcher]

    @extend_schema(
        summary="Скасувати бронювання",
        responses={204: None, 403: ErrorResponseSerializer, 404: ErrorResponseSerializer}
    )
    def delete(self, request, pk, format=None):
        # Заглушка. В майбутньому:
        # booking = self.get_object(pk)
        # booking.status = 'cancelled'
        # booking.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


class UserBookingsAPIView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Бронювання поточного користувача",
        parameters=[
            OpenApiParameter(name='limit', type=int, default=10),
            OpenApiParameter(name='next_cursor', type=str, description="Пагінація за курсором"),
        ],
        responses={200: BookingResponseSerializer(many=True)}
    )
    def get(self, request, format=None):
        mock_data = [{
            "id": 101,
            "room_id": 1,
            "start_time": "2026-10-02T10:00:00Z",
            "end_time": "2026-10-02T11:30:00Z",
            "title": "Зустріч SpaceOps",
            "status": "active"
        }]
        return Response(mock_data, status=status.HTTP_200_OK)

