"""
Сервіс управління бронюваннями (створення, скасування, зміна аудиторії).
Цей модуль містить транзакції бази даних та побічні ефекти (сповіщення, аудит).

Примітка щодо використання ШІ: модуль утворено шляхом рефакторингу
(винесення транзакцій із views.py) за допомогою ШІ-асистента.
"""

from django.db import transaction, IntegrityError
from api.models import Booking, AuditLog, Notification, User


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
