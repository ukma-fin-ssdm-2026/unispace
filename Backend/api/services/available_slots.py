from datetime import datetime, time, timedelta

from django.utils import timezone

from api.models import Booking


def get_occupied_intervals(room, selected_date):
    """
    Повертає активні бронювання аудиторії за вибрану дату як список кортежів ("HH:MM", "HH:MM").

    Бронювання, що виходить за межі доби, обрізається: початок "00:00", кінець "24:00".
    Скасовані бронювання не враховуються.
    """
    # Межі вибраної дати в часовому поясі Django
    start_datetime = timezone.make_aware(datetime.combine(selected_date, time.min))
    end_datetime = timezone.make_aware(datetime.combine(selected_date + timedelta(days=1), time.min))

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

    return occupied_intervals


def find_free_slots(bookings, day_start, day_end):
    """
    Повертає вільні проміжки часу між бронюваннями.

    bookings: список кортежів (початок, кінець)
    day_start: початок доступного періоду
    day_end: кінець доступного періоду
    """

    bookings = sorted(bookings, key=lambda booking: booking[0])

    free_slots = []
    current_time = day_start

    for start, end in bookings:
        # Ігноруємо бронювання поза доступним періодом
        if end <= day_start or start >= day_end:
            continue

        # Обмежуємо бронювання межами дня
        start = max(start, day_start)
        end = min(end, day_end)

        # Якщо перед бронюванням є вільний час
        if start > current_time:
            free_slots.append(f"{current_time}-{start}")

        # Пересуваємо поточний час уперед
        current_time = max(current_time, end)

    # Додаємо вільний час після останнього бронювання
    if current_time < day_end:
        free_slots.append(f"{current_time}-{day_end}")

    return free_slots
