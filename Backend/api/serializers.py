"""
Примітка щодо використання ШІ:
Цей модуль написано за допомогою ШІ (Gemini).
ШІ використовувався для практичної адаптації та реалізації попередньо спланованого командою
CRUD-інтерфейсу під технічний стек нашого проєкту (Django REST Framework).
Зокрема, інструмент допоміг із генерацією OpenAPI-анотацій (@extend_schema), структуруванням
серіалізаторів та оформленням mock-даних згідно з вимогами підходу Code-First.
Увесь код верифіковано, перевірено на відповідність стандартам REST-семантики та затверджено Backend Lead.
"""

from drf_spectacular.utils import extend_schema_serializer, OpenApiExample
from rest_framework import serializers


# --- Узгоджена структура помилок ---
class ErrorDetailSerializer(serializers.Serializer):
    field = serializers.CharField(help_text="Поле з помилкою")
    message = serializers.CharField(help_text="Опис помилки")
    provided_value = serializers.JSONField(required=False)


class ErrorSchemaSerializer(serializers.Serializer):
    code = serializers.CharField(default="VALIDATION_ERROR")
    message = serializers.CharField()
    details = ErrorDetailSerializer(many=True, required=False)
    request_id = serializers.CharField(default="req_abc123")
    documentation = serializers.URLField()


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "Приклад помилки валідації",
            value={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Запит містить невалідні поля",
                    "details": [{"field": "start_time", "message": "Час початку має бути раніше часу закінчення."}],
                    "request_id": "req_abc123",
                    "documentation": "https://api.unispace.com/docs/errors#validation",
                }
            },
        )
    ]
)
class ErrorResponseSerializer(serializers.Serializer):
    error = ErrorSchemaSerializer()


# --- Ресурс: Аудиторії (Rooms) ---
class RoomSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(max_length=50, help_text="Назва або номер аудиторії (напр., 4-230)")
    capacity = serializers.IntegerField(min_value=1, help_text="Місткість")
    has_projector = serializers.BooleanField()


class AvailableSlotsResponseSerializer(serializers.Serializer):
    room_id = serializers.IntegerField()
    date = serializers.DateField()
    available_slots = serializers.ListField(child=serializers.CharField())


# --- Валідатори GET-параметрів ---
class RoomQuerySerializer(serializers.Serializer):
    limit = serializers.IntegerField(min_value=1, default=20, help_text="Кількість записів")
    offset = serializers.IntegerField(min_value=0, default=0, help_text="Зсув")
    capacity = serializers.IntegerField(min_value=1, required=False, help_text="Мінімальна місткість")


class AvailableSlotsQuerySerializer(serializers.Serializer):
    room_id = serializers.IntegerField(min_value=1, required=True)
    date = serializers.DateField(required=True)


class UserBookingsQuerySerializer(serializers.Serializer):
    limit = serializers.IntegerField(min_value=1, default=10)
    next_cursor = serializers.CharField(required=False, help_text="Пагінація за курсором")


# --- Ресурс: Бронювання (Bookings) ---
@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "Приклад вхідних даних для бронювання",
            value={
                "room_id": 1,
                "start_time": "2026-10-02T10:00:00Z",
                "end_time": "2026-10-02T11:30:00Z",
                "title": "Зустріч команди SpaceOps",
            },
        )
    ]
)
class BookingCreateSerializer(serializers.Serializer):
    room_id = serializers.IntegerField(min_value=1, help_text="ID аудиторії")
    start_time = serializers.DateTimeField()
    end_time = serializers.DateTimeField()
    title = serializers.CharField(max_length=100, help_text="Тема або назва пари")

    def validate(self, data):
        if data["start_time"] >= data["end_time"]:
            raise serializers.ValidationError("Час початку має бути раніше часу закінчення.")
        return data


class BookingResponseSerializer(BookingCreateSerializer):
    id = serializers.IntegerField(read_only=True)
    status = serializers.CharField(default="booked")
