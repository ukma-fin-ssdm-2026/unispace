from datetime import datetime, timedelta, timezone


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
