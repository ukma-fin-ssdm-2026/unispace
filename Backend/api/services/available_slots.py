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
