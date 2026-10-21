"""Доменні функції планування аудиторій (чисті функції, без звернень до бази даних)."""

from datetime import datetime


def intervals_overlap(start1: datetime, end1: datetime, start2: datetime, end2: datetime) -> bool:
    """
    Чи перетинаються два часові проміжки [start, end).

    Кінець проміжку в нього не входить, тому пари, що йдуть одна за одною (10:00-11:00 і 11:00-12:00),
    не перетинаються - так само, як у ExclusionConstraint моделі Booking.
    """
    if any(moment.tzinfo is None for moment in (start1, end1, start2, end2)):
        raise ValueError("Час має бути з часовим поясом")
    first_starts_before_second_ends = start1 < end2
    second_starts_before_first_ends = start2 < end1
    return first_starts_before_second_ends and second_starts_before_first_ends
