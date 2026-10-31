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

Підбір вільних аудиторій (BookingAlternativesAPIView) згенеровано ШІ (Claude) за тестами
test_room_alternatives.py, які закомічено раніше за реалізацію.
"""

import uuid

from django.db.models import Prefetch
from django.db.models import ProtectedError
from drf_spectacular.utils import extend_schema

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, BasePermission, IsAuthenticated

from .models import AuditLog, Room, Booking, Lesson, SyncLog, User
from api.services import bookings, schedule
from api.services.room_suggestions import suggest_rooms

from datetime import datetime, time, timedelta
from django.utils import timezone
from api.services.available_slots import find_free_slots

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
    ScheduleItemSerializer,
    ScheduleQuerySerializer,
    RoomWriteSerializer,
    BookingChangeRoomSerializer,
    RoomAlternativesQuerySerializer,
)

# ==========================================
# Дозволи (Permissions)
# ==========================================


class IsTeacherOrDispatcher(BasePermission):
    """
    Only authenticated teachers and dispatchers
    can create or delete bookings.
    """

    message = "Only teachers and dispatchers can manage bookings."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and getattr(user, "role", None) in ("teacher", "dispatcher"))


class IsDispatcher(BasePermission):
    message = "Only dispatchers can access sync logs."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and getattr(user, "role", None) == "dispatcher")

    # ==========================================
    # Допоміжні функції (Форматування відповідей)
    # ==========================================


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


# Допоміжна функція для відповідей з помилками, які не є помилками валідації (403, 404, 409)
def get_error_response(code, message, anchor):
    return {
        "error": {
            "code": code,
            "message": message,
            "request_id": "req_abc123",
            "documentation": f"https://api.unispace.com/docs/errors#{anchor}",
        }
    }


def not_found_response(entity, pk):
    message = f"{entity} з ID {pk} не знайдено"
    return Response(get_error_response("NOT_FOUND", message, "not-found"), status=status.HTTP_404_NOT_FOUND)


def conflict_response(message):
    return Response(get_error_response("CONFLICT", message, "conflict"), status=status.HTTP_409_CONFLICT)


def forbidden_response(message):
    return Response(get_error_response("FORBIDDEN", message, "forbidden"), status=status.HTTP_403_FORBIDDEN)


def unknown_reference_response(field, entity):
    """400 для ID у тілі запиту, за яким у базі нічого немає."""
    errors = {field: [f"{entity} з таким ID не знайдено."]}
    return Response(get_validation_error_response(errors), status=status.HTTP_400_BAD_REQUEST)


def can_manage_lesson(user, lesson):
    """Диспетчер керує будь-якими заняттями, викладач - лише власними."""
    return user.role == User.RoleChoices.DISPATCHER or lesson.teacher_id == user.id

    # ==========================================
    # API Аудиторій (Rooms)
    # ==========================================


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


class RoomDetailAPIView(APIView):
    def get_permissions(self):
        # Перегляд відкритий усім, редагування і видалення - лише диспетчеру (FR-008).
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsDispatcher()]

    @extend_schema(
        summary="Отримати аудиторію",
        responses={200: RoomSerializer, 404: ErrorResponseSerializer},
    )
    def get(self, request, pk, format=None):
        room = Room.objects.filter(pk=pk).first()
        if room is None:
            return not_found_response("Аудиторію", pk)

        return Response(RoomSerializer(room).data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Оновити аудиторію",
        request=RoomWriteSerializer,
        responses={
            200: RoomSerializer,
            400: ErrorResponseSerializer,
            403: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
        },
    )
    def patch(self, request, pk, format=None):
        room = Room.objects.filter(pk=pk).first()
        if room is None:
            return not_found_response("Аудиторію", pk)

        serializer = RoomWriteSerializer(room, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(get_validation_error_response(serializer.errors), status=status.HTTP_400_BAD_REQUEST)

        room = serializer.save()
        return Response(RoomSerializer(room).data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Видалити аудиторію",
        description="Аудиторію з бронюваннями, конфліктами чи записами аудиту видалити не можна.",
        responses={204: None, 403: ErrorResponseSerializer, 404: ErrorResponseSerializer, 409: ErrorResponseSerializer},
    )
    def delete(self, request, pk, format=None):
        room = Room.objects.filter(pk=pk).first()
        if room is None:
            return not_found_response("Аудиторію", pk)

        try:
            room.delete()
        except ProtectedError:
            return conflict_response("Аудиторію не можна видалити: з нею повʼязані бронювання або записи аудиту")

        return Response(status=status.HTTP_204_NO_CONTENT)


class AvailableSlotsAPIView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Пошук вільних слотів",
        parameters=[AvailableSlotsQuerySerializer],
        responses={
            200: AvailableSlotsResponseSerializer,
            400: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
        },
    )
    def get(self, request, format=None):
        query = AvailableSlotsQuerySerializer(data=request.query_params)

        if not query.is_valid():
            return Response(
                get_validation_error_response(query.errors),
                status=status.HTTP_400_BAD_REQUEST,
            )

        room_id = query.validated_data["room_id"]
        selected_date = query.validated_data["date"]

        # Перевіряємо, чи існує аудиторія
        room = Room.objects.filter(pk=room_id).first()

        if room is None:
            return not_found_response("Аудиторію", room_id)

        # Недоступна аудиторія не має вільних слотів
        if not room.is_available:
            return Response(
                {
                    "room_id": room_id,
                    "date": selected_date,
                    "available_slots": [],
                },
                status=status.HTTP_200_OK,
            )

        # Тимчасові межі доступності аудиторії
        day_start = "08:00"
        day_end = "20:00"

        # Межі вибраної дати в часовому поясі Django
        next_date = selected_date + timedelta(days=1)

        start_datetime = timezone.make_aware(datetime.combine(selected_date, time.min))
        end_datetime = timezone.make_aware(datetime.combine(next_date, time.min))

        # Знаходимо тільки активні бронювання цієї аудиторії
        bookings = Booking.objects.filter(
            room=room,
            status=Booking.BookingStatus.ACTIVE,
            start_time__lt=end_datetime,
            end_time__gt=start_datetime,
        ).order_by("start_time")

        occupied_intervals = []

        for booking in bookings:
            # Обрізаємо бронювання до меж вибраної дати
            booking_start = max(booking.start_time, start_datetime)
            booking_end = min(booking.end_time, end_datetime)

            local_start = timezone.localtime(booking_start)
            local_end = timezone.localtime(booking_end)

            start_str = "00:00" if booking_start == start_datetime else local_start.strftime("%H:%M")
            end_str = "24:00" if booking_end == end_datetime else local_end.strftime("%H:%M")

            occupied_intervals.append((start_str, end_str))

        # Обчислюємо вільні проміжки
        free_slots = find_free_slots(
            occupied_intervals,
            day_start,
            day_end,
        )

        return Response(
            {
                "room_id": room_id,
                "date": selected_date,
                "available_slots": free_slots,
            },
            status=status.HTTP_200_OK,
        )


class BookingListCreateAPIView(APIView):
    permission_classes = [IsTeacherOrDispatcher]

    @extend_schema(
        summary="Створити бронювання",
        request=BookingCreateSerializer,
        responses={
            201: BookingResponseSerializer,
            400: ErrorResponseSerializer,
            403: ErrorResponseSerializer,
            409: ErrorResponseSerializer,
        },
    )
    def post(self, request, format=None):
        serializer = BookingCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(get_validation_error_response(serializer.errors), status=status.HTTP_400_BAD_REQUEST)

        lesson = Lesson.objects.filter(pk=serializer.validated_data["lesson_id"]).first()
        if lesson is None:
            return unknown_reference_response("lesson_id", "Заняття")

        room = Room.objects.filter(pk=serializer.validated_data["room_id"]).first()
        if room is None:
            return unknown_reference_response("room_id", "Аудиторію")

        if not can_manage_lesson(request.user, lesson):
            return forbidden_response("Викладач може бронювати аудиторії лише для власних занять")

        if not room.is_available:
            return conflict_response("Аудиторія недоступна для використання")

        try:
            booking = bookings.create_booking(lesson, room, request.user)
            return Response(BookingResponseSerializer(booking).data, status=status.HTTP_201_CREATED)
        except bookings.BookingConflictError as e:
            return conflict_response(str(e))


class BookingDetailAPIView(APIView):
    permission_classes = [IsTeacherOrDispatcher]

    @extend_schema(
        summary="Отримати бронювання",
        responses={200: BookingResponseSerializer, 403: ErrorResponseSerializer, 404: ErrorResponseSerializer},
    )
    def get(self, request, pk, format=None):
        booking = Booking.objects.select_related("lesson").filter(pk=pk).first()
        if booking is None:
            return not_found_response("Бронювання", pk)

        if not can_manage_lesson(request.user, booking.lesson):
            return forbidden_response("Викладач бачить лише бронювання власних занять")

        return Response(BookingResponseSerializer(booking).data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Скасувати бронювання",
        description="Бронювання не видаляється: отримує статус cancelled, у журнал аудиту додається запис.",
        responses={204: None, 403: ErrorResponseSerializer, 404: ErrorResponseSerializer},
    )
    def delete(self, request, pk, format=None):
        booking = Booking.objects.select_related("lesson", "room").filter(pk=pk).first()
        if booking is None:
            return not_found_response("Бронювання", pk)

        if not can_manage_lesson(request.user, booking.lesson):
            return forbidden_response("Викладач може скасовувати лише бронювання власних занять")

        bookings.cancel_booking(booking, request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class BookingAlternativesAPIView(APIView):
    permission_classes = [IsTeacherOrDispatcher]

    @extend_schema(
        summary="Підібрати вільні аудиторії для заміни",
        description=(
            "Аудиторії, вільні на час заняття: доступні, не менші за потрібну місткість і без активних бронювань, "
            "що перетинаються з заняттям. Спершу аудиторії бажаного корпусу, далі - за найменшою достатньою місткістю."
        ),
        parameters=[RoomAlternativesQuerySerializer],
        responses={
            200: RoomSerializer(many=True),
            400: ErrorResponseSerializer,
            403: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
            409: ErrorResponseSerializer,
        },
    )
    def get(self, request, pk, format=None):
        booking = Booking.objects.select_related("lesson", "room").filter(pk=pk).first()
        if booking is None:
            return not_found_response("Бронювання", pk)

        if not can_manage_lesson(request.user, booking.lesson):
            return forbidden_response("Викладач може підбирати аудиторії лише для власних занять")

        query = RoomAlternativesQuerySerializer(data=request.query_params)
        if not query.is_valid():
            return Response(get_validation_error_response(query.errors), status=status.HTTP_400_BAD_REQUEST)

        if booking.status != Booking.BookingStatus.ACTIVE:
            return conflict_response("Для скасованого бронювання аудиторію не підбирають")

        rooms = suggest_rooms(
            Room.objects.all(),
            min_capacity=query.validated_data.get("min_capacity", booking.room.capacity),
            busy_room_ids=bookings.busy_room_ids(booking),
            preferred_building=query.validated_data.get("building", booking.room.building),
        )
        return Response(RoomSerializer(rooms, many=True).data, status=status.HTTP_200_OK)


class BookingChangeRoomAPIView(APIView):
    permission_classes = [IsTeacherOrDispatcher]

    @extend_schema(
        summary="Змінити аудиторію бронювання",
        description="Переносить заняття в іншу аудиторію, пише запис в аудит і сповіщає групу.",
        request=BookingChangeRoomSerializer,
        responses={
            200: BookingResponseSerializer,
            400: ErrorResponseSerializer,
            403: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
            409: ErrorResponseSerializer,
        },
    )
    def post(self, request, pk, format=None):
        booking = Booking.objects.select_related("lesson__group", "room").filter(pk=pk).first()
        if booking is None:
            return not_found_response("Бронювання", pk)

        if not can_manage_lesson(request.user, booking.lesson):
            return forbidden_response("Викладач може змінювати аудиторію лише власних занять")

        serializer = BookingChangeRoomSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(get_validation_error_response(serializer.errors), status=status.HTTP_400_BAD_REQUEST)

        if booking.status != Booking.BookingStatus.ACTIVE:
            return conflict_response("Скасоване бронювання змінити не можна")

        new_room = Room.objects.filter(pk=serializer.validated_data["room_id"]).first()
        if new_room is None:
            return unknown_reference_response("room_id", "Аудиторію")

        if new_room.pk == booking.room_id:
            errors = {"room_id": ["Заняття вже призначене в цій аудиторії."]}
            return Response(get_validation_error_response(errors), status=status.HTTP_400_BAD_REQUEST)

        if not new_room.is_available:
            return conflict_response("Аудиторія недоступна для використання")

        try:
            booking = bookings.change_booking_room(booking, new_room, serializer.validated_data["reason"], request.user)
            return Response(BookingResponseSerializer(booking).data, status=status.HTTP_200_OK)
        except bookings.BookingConflictError as e:
            return conflict_response(str(e))


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

        user_bookings = Booking.objects.filter(user=request.user).order_by("-start_time")
        limit = query.validated_data.get("limit", 10)
        user_bookings = user_bookings[:limit]

        serializer = BookingResponseSerializer(user_bookings, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # ==========================================
    # API Розкладу (Schedule)
    # ==========================================


class ScheduleAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Розклад занять",
        description=(
            "Студент бачить розклад своєї групи, викладач - власні заняття, диспетчер - будь-які "
            "(з можливістю відфільтрувати за групою). Тільки для читання."
        ),
        parameters=[ScheduleQuerySerializer],
        responses={200: ScheduleItemSerializer(many=True), 400: ErrorResponseSerializer},
    )
    def get(self, request, format=None):
        query = ScheduleQuerySerializer(data=request.query_params)
        if not query.is_valid():
            return Response(get_validation_error_response(query.errors), status=status.HTTP_400_BAD_REQUEST)

        room_changes = AuditLog.objects.filter(action="room_changed")
        active_bookings = (
            Booking.objects.filter(status=Booking.BookingStatus.ACTIVE)
            .select_related("room")
            .prefetch_related(Prefetch("audit_logs", queryset=room_changes, to_attr="room_changes"))
        )
        lessons = Lesson.objects.select_related("group", "teacher").prefetch_related(
            Prefetch("bookings", queryset=active_bookings, to_attr="active_bookings")
        )
        lessons = schedule.limit_lessons_to_user(lessons, request.user, query.validated_data.get("group_id"))

        date_from = query.validated_data.get("date_from")
        if date_from:
            lessons = lessons.filter(date__gte=date_from)

        date_to = query.validated_data.get("date_to")
        if date_to:
            lessons = lessons.filter(date__lte=date_to)

        offset = query.validated_data["offset"]
        limit = query.validated_data["limit"]
        lessons = lessons[offset : offset + limit]

        serializer = ScheduleItemSerializer([schedule.build_schedule_item(lesson) for lesson in lessons], many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


# ==========================================
# API Синхронізації (Sync)
# ==========================================


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
