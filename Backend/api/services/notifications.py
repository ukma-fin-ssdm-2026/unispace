"""
Сервіс для генерації та відправки сповіщень.

Примітка щодо використання ШІ: код цього модуля згенеровано за допомогою ШІ
для реалізації вимог FR-015 та TP-01. Код верифіковано та адаптовано відповідно до бізнес-логіки проєкту.
"""

from django.utils import timezone

# ==========================================
# Генерація Email-шаблонів
# ==========================================


def generate_room_change_email_body(booking, previous_room, new_room):
    """
    Генерує текст Email-сповіщення про зміну аудиторії (FR-015).
    Містить назву дисципліни, час, аудиторії «було → стало» та room_id нової аудиторії.
    """
    subject = booking.lesson.subject
    teacher_name = booking.lesson.teacher.full_name
    start_time_str = timezone.localtime(booking.start_time).strftime("%d.%m.%Y %H:%M")

    # Використовуємо room_id з користю: генеруємо посилання, а не показуємо сирий UUID
    room_link = f"https://unispace.com/rooms/{new_room.id}"

    body = (
        f"Шановний студенте,\n\n"
        f"Аудиторію для заняття «{subject}» ({start_time_str}), яке викладає {teacher_name}, було змінено.\n\n"
        f"Попередня аудиторія: {previous_room.number}\n"
        f"Нова аудиторія: {new_room.number}\n\n"
        f"Переглянути деталі аудиторії: {room_link}\n\n"
        f"З повагою, Команда UniSpace"
    )
    return body


# TODO: у майбутньому можна буде додати функцію відправки через SMTP (send_mail).
