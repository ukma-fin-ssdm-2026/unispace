"""
Сервіс управління бронюваннями (створення, скасування, зміна аудиторії).
Цей модуль містить транзакції бази даних та побічні ефекти (сповіщення, аудит).

Примітка щодо використання ШІ: модуль утворено шляхом рефакторингу
(винесення транзакцій із views.py) за допомогою ШІ-асистента.
"""

from datetime import timedelta

from django.db import transaction, IntegrityError
from api.models import Booking, AuditLog, Notification, User

from .scheduling import intervals_overlap

# Бронювання не триває довше доби, тож кандидатів на перетин досить шукати в цьому вікні.
_OVERLAP_SEARCH_WINDOW = timedelta(days=1)


class BookingConflictError(Exception):
    """Помилка бази даних через конфлікт (наприклад, накладка часу)."""

    # ==========================================
    # Основні транзакції бронювання
    # ==========================================


def create_booking(lesson, room, user):
    """Створює нове бронювання у межах транзакції."""
    try:
        with transaction.atomic():
            return Booking.objects.create(lesson=lesson, room=room, user=user)
    except IntegrityError as e:
        raise BookingConflictError(
            "Аудиторія вже заброньована на цей час або заняття вже має активне бронювання"
        ) from e


def cancel_booking(booking, user):
    """Скасовує бронювання та створює запис аудиту."""
    if booking.status == Booking.BookingStatus.ACTIVE:
        with transaction.atomic():
            booking.status = Booking.BookingStatus.CANCELLED
            booking.save(update_fields=["status", "updated_at"])
            AuditLog.objects.create(
                booking=booking,
                user=user,
                action="cancelled",
                previous_room=booking.room,
            )
    return booking


def change_booking_room(booking, new_room, reason, user):
    """Переносить заняття в іншу аудиторію, пише аудит і сповіщає студентів."""
    previous_room = booking.room
    try:
        with transaction.atomic():
            booking.room = new_room
            booking.save(update_fields=["room", "updated_at"])
            AuditLog.objects.create(
                booking=booking,
                user=user,
                action="room_changed",
                previous_room=previous_room,
                new_room=new_room,
                reason=reason,
            )
            _notify_group(booking, previous_room, new_room)
        return booking
    except IntegrityError as e:
        raise BookingConflictError("Нова аудиторія вже заброньована на цей час") from e


def busy_room_ids(booking):
    """
    ID аудиторій, зайнятих на час бронювання (FR-010): активні бронювання, що перетинаються з ним
    за правилом intervals_overlap ([start, end)), плюс поточна аудиторія самого бронювання.

    База лише звужує вибірку до вікна навколо заняття, а сам перетин визначає доменна функція,
    тож правило «пари впритул не перетинаються» реалізовано в одному місці (scheduling.py).
    """
    candidates = (
        Booking.objects.filter(
            status=Booking.BookingStatus.ACTIVE,
            start_time__lt=booking.end_time,
            start_time__gte=booking.start_time - _OVERLAP_SEARCH_WINDOW,
        )
        .exclude(pk=booking.pk)
        .only("room_id", "start_time", "end_time")
    )
    busy = {
        other.room_id
        for other in candidates
        if intervals_overlap(booking.start_time, booking.end_time, other.start_time, other.end_time)
    }
    busy.add(booking.room_id)
    return busy

    # ==========================================
    # Допоміжні функції (Сповіщення)
    # ==========================================


def _notify_group(booking, previous_room, new_room):
    """Створює сповіщення для кожного користувача академічної групи заняття (FR-015)."""
    message = (
        f"Заняття «{booking.lesson.subject}» ({booking.start_time:%d.%m.%Y %H:%M}) "
        f"перенесено: {previous_room} → {new_room}"
    )
    recipients = User.objects.filter(group=booking.lesson.group)
    Notification.objects.bulk_create(
        [Notification(user=user, type="room_changed", message=message) for user in recipients]
    )
