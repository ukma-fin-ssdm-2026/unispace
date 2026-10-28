"""
Доменні правила бронювання, перевірки лімітів та місткості.
Цей модуль містить чисту бізнес-логіку.

Примітка щодо використання ШІ: модуль утворено шляхом рефакторингу та
об'єднання розпорошених бізнес-правил (з utils.py, validators.py та
старого booking_rules.py) в єдиний сервісний шар за допомогою ШІ-асистента.
"""

from datetime import datetime, timedelta, timezone, time
from .scheduling import _require_timezone

RECENT_CHANGE_HOURS = 24
MAX_LESSON_MINUTES = 90


class BookingRuleError(ValueError):
    """Порушено бізнес-правило бронювання."""

    # ==========================================
    # Правила часу та тривалості
    # ==========================================


def booking_duration(start_time: datetime, end_time: datetime) -> timedelta:
    """
    Обчислює тривалість бронювання.
    Генерує BookingRuleError, якщо немає часового поясу або час некоректний.
    """

    try:
        _require_timezone(start_time, end_time)
    except ValueError as e:
        raise BookingRuleError(str(e))

    duration = end_time.astimezone(timezone.utc) - start_time.astimezone(timezone.utc)
    if duration <= timedelta(0):
        raise BookingRuleError("Час завершення має бути пізніше за час початку.")
    return duration


def is_valid_lesson_duration(start_time: time, end_time: time) -> bool:
    """Перевіряє, що час заняття коректний і не перевищує ліміт."""

    if start_time >= end_time:
        return False

    duration_minutes = (end_time.hour * 60 + end_time.minute) - (start_time.hour * 60 + start_time.minute)
    return duration_minutes <= MAX_LESSON_MINUTES


def is_recently_changed(change_times: list[datetime], lesson_start: datetime) -> bool:
    """Чи змінювали аудиторію менш ніж за 24 години до початку заняття (маркер «Змінено», FR-006)."""

    try:
        _require_timezone(lesson_start)
    except ValueError as e:
        raise BookingRuleError(str(e))

    threshold = lesson_start - timedelta(hours=RECENT_CHANGE_HOURS)
    return any(threshold < changed_at <= lesson_start for changed_at in change_times)

    # ==========================================
    # Правила місткості
    # ==========================================


def validate_attendees_fit_room(attendees: int, capacity: int) -> None:
    """Перевіряє, чи вміщуються учасники, і генерує BookingRuleError, якщо ні."""

    if attendees < 1:
        raise BookingRuleError("Кількість учасників має бути не меншою за 1.")
    if capacity < 1:
        raise BookingRuleError("Місткість аудиторії має бути не меншою за 1.")
    if attendees > capacity:
        raise BookingRuleError("Кількість учасників перевищує місткість аудиторії.")
