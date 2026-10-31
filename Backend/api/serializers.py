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

from drf_spectacular.utils import extend_schema_serializer, OpenApiExample
from rest_framework import serializers
from .models import Room


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
                    "details": [{"field": "lesson_id", "message": "Обов'язкове поле."}],
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
class RoomSerializer(serializers.ModelSerializer):
    class Meta:
        model = Room
        fields = ["id", "building", "number", "capacity", "has_computers", "projector_working", "is_available"]

        extra_kwargs = {
            "number": {"help_text": "Назва або номер аудиторії (напр., 4-230)"},
            "capacity": {"help_text": "Місткість (кількість посадкових місць)"},
        }


class RoomWriteSerializer(serializers.ModelSerializer):
    """Вхідні дані для створення й редагування аудиторії диспетчером (FR-008)."""

    class Meta:
        model = Room
        fields = ["building", "number", "capacity", "board_type", "projector_working", "has_computers", "is_available"]

        extra_kwargs = {
            "number": {"help_text": "Назва або номер аудиторії (напр., 4-230)"},
            "capacity": {"min_value": 1, "help_text": "Місткість (кількість посадкових місць)"},
        }


class AvailableSlotsResponseSerializer(serializers.Serializer):
    room_id = serializers.UUIDField()
    date = serializers.DateField()
    available_slots = serializers.ListField(child=serializers.CharField())


# --- Валідатори GET-параметрів ---
class RoomQuerySerializer(serializers.Serializer):
    limit = serializers.IntegerField(min_value=1, default=20, help_text="Кількість записів")
    offset = serializers.IntegerField(min_value=0, default=0, help_text="Зсув")
    capacity = serializers.IntegerField(min_value=1, required=False, help_text="Мінімальна місткість")
    building = serializers.CharField(required=False, help_text="Корпус")
    projector_working = serializers.BooleanField(
        required=False, allow_null=True, help_text="Лише аудиторії зі справним проєктором"
    )
    has_computers = serializers.BooleanField(required=False, allow_null=True, help_text="Лише аудиторії з комп'ютерами")


class AvailableSlotsQuerySerializer(serializers.Serializer):
    room_id = serializers.UUIDField(required=True)
    date = serializers.DateField(required=True)


class RoomAlternativesQuerySerializer(serializers.Serializer):
    """Параметри підбору вільних аудиторій для заміни (FR-010)."""

    min_capacity = serializers.IntegerField(
        min_value=1, required=False, help_text="Мінімальна місткість; за замовчуванням - місткість поточної аудиторії"
    )
    building = serializers.CharField(
        max_length=20, required=False, help_text="Бажаний корпус; за замовчуванням - корпус поточної аудиторії"
    )
    expand = serializers.BooleanField(
        required=False,
        default=False,
        help_text="false - лише бажаний корпус (FR-010); true - розширити пошук на інші корпуси",
    )


class RoomAlternativesResponseSerializer(serializers.Serializer):
    """Результат підбору: аудиторії та повідомлення, якщо варіантів немає (FR-010, US-10)."""

    building = serializers.CharField(help_text="Корпус, з якого почали пошук")
    expanded = serializers.BooleanField(help_text="Чи розширено пошук на інші корпуси")
    rooms = RoomSerializer(many=True, help_text="Вільні аудиторії: спершу бажаний корпус, далі найменша місткість")
    message = serializers.CharField(allow_null=True, help_text="Пояснення, якщо вільних аудиторій немає; інакше null")


class UserBookingsQuerySerializer(serializers.Serializer):
    limit = serializers.IntegerField(min_value=1, default=10)
    next_cursor = serializers.CharField(required=False, help_text="Пагінація за курсором")


# --- Ресурс: Бронювання (Bookings) ---
@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "Приклад вхідних даних для бронювання",
            value={
                "room_id": "123e4567-e89b-12d3-a456-426614174000",
                "lesson_id": "987f6543-e21b-34c1-b567-112233445566",
            },
        )
    ]
)
class BookingCreateSerializer(serializers.Serializer):
    room_id = serializers.UUIDField(help_text="ID аудиторії")
    lesson_id = serializers.UUIDField(help_text="ID заняття")


class BookingChangeRoomSerializer(serializers.Serializer):
    room_id = serializers.UUIDField(help_text="ID нової аудиторії")
    reason = serializers.CharField(required=False, allow_blank=True, default="", help_text="Причина зміни аудиторії")


class BookingResponseSerializer(BookingCreateSerializer):
    id = serializers.UUIDField(read_only=True)
    status = serializers.ChoiceField(choices=["active", "cancelled"], read_only=True)
    title = serializers.CharField(source="lesson.subject", read_only=True, help_text="Назва дисципліни")
    start_time = serializers.DateTimeField(read_only=True)
    end_time = serializers.DateTimeField(read_only=True)


class SyncLogSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    started_at = serializers.DateTimeField(help_text="Час початку синхронізації")
    finished_at = serializers.DateTimeField(required=False, allow_null=True, help_text="Час завершення синхронізації")
    status = serializers.ChoiceField(
        choices=["in_progress", "success", "failed"], help_text="Поточний статус синхронізації"
    )
    trigger = serializers.ChoiceField(
        choices=["manual", "scheduled"], help_text="Джерело запуску (ручний диспетчером чи за розкладом)"
    )
    error_message = serializers.CharField(
        required=False, allow_null=True, help_text="Текст помилки парсингу або мережі, якщо статус failed"
    )


# --- Ресурс: Розклад (Schedule) ---
class ScheduleQuerySerializer(serializers.Serializer):
    date_from = serializers.DateField(required=False, help_text="Початок періоду (включно)")
    date_to = serializers.DateField(required=False, help_text="Кінець періоду (включно)")
    group_id = serializers.UUIDField(required=False, help_text="Група (лише для диспетчера)")
    limit = serializers.IntegerField(min_value=1, max_value=200, default=50, help_text="Кількість записів")
    offset = serializers.IntegerField(min_value=0, default=0, help_text="Зсув")

    def validate(self, attrs):
        date_from = attrs.get("date_from")
        date_to = attrs.get("date_to")
        if date_from and date_to and date_from > date_to:
            raise serializers.ValidationError("Початок періоду не може бути пізніше за його кінець.")
        return attrs


class ScheduleRoomSerializer(serializers.ModelSerializer):
    class Meta:
        model = Room
        fields = ["id", "building", "number"]


class ScheduleItemSerializer(serializers.Serializer):
    lesson_id = serializers.UUIDField()
    subject = serializers.CharField(help_text="Назва дисципліни")
    date = serializers.DateField()
    start_time = serializers.TimeField()
    end_time = serializers.TimeField()
    group = serializers.CharField(help_text="Назва академічної групи")
    teacher = serializers.CharField(help_text="Імʼя викладача")
    room = ScheduleRoomSerializer(allow_null=True, help_text="Призначена аудиторія або null")
    room_assigned = serializers.BooleanField(help_text="false, якщо бронювання скасовано або його немає")
    room_changed = serializers.BooleanField(
        help_text="Маркер «Змінено»: аудиторію змінено менш ніж за 24 години до початку заняття"
    )


# --- Ресурс: Попередня пара в аудиторії (FR-019) ---
class PreviousLessonSerializer(serializers.Serializer):
    subject = serializers.CharField(help_text="Назва дисципліни")
    group = serializers.CharField(help_text="Назва академічної групи")
    teacher = serializers.CharField(help_text="ПІБ викладача попереднього заняття")
    start_time = serializers.DateTimeField(help_text="Початок попереднього заняття")
    end_time = serializers.DateTimeField(help_text="Завершення попереднього заняття")


class PreviousLessonResponseSerializer(serializers.Serializer):
    previous_lesson = PreviousLessonSerializer(
        allow_null=True, help_text="Попереднє заняття в цій аудиторії того ж дня або null"
    )
    message = serializers.CharField(
        allow_null=True, help_text="«Попередньої пари не було», якщо previous_lesson = null"
    )
