"""
Логіка визначення попередніх занять в аудиторії для відстежування ключів від неї.

Примітка щодо використання ШІ: код написано за участі ШІ-асистента
та перевірено за стандартами забезпечення якості UniSpace. Верифіковано людиною (Тимохина Ксенія)
"""

from datetime import date
from typing import Iterable, List, Optional

from api.models import Booking


def get_day_bookings(room_id: int, target_date: date) -> List[Booking]:
    """
    Повертає всі активні бронювання для вказаної аудиторії за конкретний день.
    Скасовані бронювання не враховуються: вони звільнили аудиторію (FR-020).
    Сортує заняття хронологічно за часом їхнього початку.
    """
    return list(
        Booking.objects.filter(
            room_id=room_id,
            start_time__date=target_date,
            status=Booking.BookingStatus.ACTIVE,
        )
        .select_related("lesson__group", "lesson__teacher")
        .order_by("start_time")
    )


def get_previous_booking(
    current_booking: Booking,
    day_bookings: Optional[Iterable[Booking]] = None,
) -> Optional[Booking]:
    """
    Повертає попереднє бронювання в тій самій аудиторії за той самий день.

    Допомагає визначити, хто останнім користувався аудиторією:
    - Якщо заняття йшли одне за одним або через перерву — повертає попереднє заняття.
    - Якщо перед поточним заняттям було «вікно» — повертає останнє заняття до вікна.
    - Якщо це перша пара дня в цій аудиторії — повертає None.
    """
    if day_bookings is None:
        target_date = current_booking.start_time.date()
        day_bookings = get_day_bookings(current_booking.room_id, target_date)

    candidates = [
        booking
        for booking in day_bookings
        if booking.room_id == current_booking.room_id
        and booking.start_time.date() == current_booking.start_time.date()
        and booking.end_time <= current_booking.start_time
        and booking.id != current_booking.id
    ]

    if not candidates:
        return None

    return max(candidates, key=lambda booking: booking.end_time)
