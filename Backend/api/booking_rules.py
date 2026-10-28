from datetime import datetime, timedelta, timezone

RECENT_CHANGE_HOURS = 24


class BookingRuleError(ValueError):
    """Порушено бізнес-правило бронювання."""


def booking_duration(start_time: datetime, end_time: datetime) -> timedelta:
    if start_time.tzinfo is None or end_time.tzinfo is None:
        raise BookingRuleError("Час бронювання має містити часовий пояс.")

    duration = end_time.astimezone(timezone.utc) - start_time.astimezone(timezone.utc)
    if duration <= timedelta(0):
        raise BookingRuleError("Час завершення має бути пізніше за час початку.")
    return duration


def validate_attendees_fit_room(attendees: int, capacity: int) -> None:
    if attendees < 1:
        raise BookingRuleError("Кількість учасників має бути не меншою за 1.")
    if capacity < 1:
        raise BookingRuleError("Місткість аудиторії має бути не меншою за 1.")
    if attendees > capacity:
        raise BookingRuleError("Кількість учасників перевищує місткість аудиторії.")


def is_recently_changed(change_times: list[datetime], lesson_start: datetime) -> bool:
    """Чи змінювали аудиторію менш ніж за 24 години до початку заняття (маркер «Змінено», FR-006)."""
    if lesson_start.tzinfo is None:
        raise BookingRuleError("Час бронювання має містити часовий пояс.")

    threshold = lesson_start - timedelta(hours=RECENT_CHANGE_HOURS)
    return any(threshold < changed_at <= lesson_start for changed_at in change_times)
