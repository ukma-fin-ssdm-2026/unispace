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

from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, BasePermission, IsAuthenticated
from drf_spectacular.utils import extend_schema
from .models import AuditLog, Room, Booking, Lesson, SyncLog, User, Notification

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
    BookingChangeRoomSerializer,
)


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

        # Накладки та друге активне бронювання заняття відсікає БД (ExclusionConstraint, UniqueConstraint).
        try:
            with transaction.atomic():
                booking = Booking.objects.create(lesson=lesson, room=room, user=request.user)
        except IntegrityError:
            return conflict_response("Аудиторія вже заброньована на цей час або заняття вже має активне бронювання")

        return Response(BookingResponseSerializer(booking).data, status=status.HTTP_201_CREATED)


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

        # Повторне скасування нічого не змінює і не дублює запис аудиту.
        if booking.status == Booking.BookingStatus.ACTIVE:
            with transaction.atomic():
                booking.status = Booking.BookingStatus.CANCELLED
                booking.save(update_fields=["status", "updated_at"])
                AuditLog.objects.create(
                    booking=booking,
                    user=request.user,
                    action="cancelled",
                    previous_room=booking.room,
                )

        return Response(status=status.HTTP_204_NO_CONTENT)


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

        previous_room = booking.room
        try:
            with transaction.atomic():
                booking.room = new_room
                booking.save(update_fields=["room", "updated_at"])
                AuditLog.objects.create(
                    booking=booking,
                    user=request.user,
                    action="room_changed",
                    previous_room=previous_room,
                    new_room=new_room,
                    reason=serializer.validated_data["reason"],
                )
                self.notify_group(booking, previous_room, new_room)
        except IntegrityError:
            return conflict_response("Нова аудиторія вже заброньована на цей час")

        return Response(BookingResponseSerializer(booking).data, status=status.HTTP_200_OK)

    @staticmethod
    def notify_group(booking, previous_room, new_room):
        """Створює сповіщення для кожного користувача академічної групи заняття (FR-015)."""
        message = (
            f"Заняття «{booking.lesson.subject}» ({booking.start_time:%d.%m.%Y %H:%M}) "
            f"перенесено: {previous_room} → {new_room}"
        )
        recipients = User.objects.filter(group=booking.lesson.group)
        Notification.objects.bulk_create(
            [Notification(user=user, type="room_changed", message=message) for user in recipients]
        )


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
