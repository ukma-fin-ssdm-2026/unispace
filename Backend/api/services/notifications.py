"""
Сервіс для генерації та відправки сповіщень.

Примітка щодо використання ШІ: код цього модуля згенеровано за допомогою ШІ
для реалізації вимог FR-015 та TP-01. Код верифіковано та адаптовано відповідно до бізнес-логіки проєкту.
"""

import logging

from django.conf import settings
from django.core.mail import send_mass_mail
from django.utils import timezone

from api.models import User

logger = logging.getLogger(__name__)

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
    room_link = f"{settings.FRONTEND_BASE_URL}/rooms/{new_room.id}"

    body = (
        f"Шановний студенте,\n\n"
        f"Аудиторію для заняття «{subject}» ({start_time_str}), яке викладає {teacher_name}, було змінено.\n\n"
        f"Попередня аудиторія: {previous_room.number}\n"
        f"Нова аудиторія: {new_room.number}\n\n"
        f"Переглянути деталі аудиторії: {room_link}\n\n"
        f"З повагою, Команда UniSpace"
    )
    return body


# ==========================================
# Відправка Email
# ==========================================


def _semester_started():
    """До початку семестру email про зміну аудиторії не надсилається (FR-015)."""
    start = settings.SEMESTER_START_DATE
    return start is None or timezone.localdate() >= start


def send_room_change_emails(booking, previous_room, new_room):
    """
    Надсилає кожному активному студенту групи заняття окремий лист про зміну аудиторії (FR-015).
    Викликається після коміту транзакції: якщо перенесення відкотилося, листів немає.
    Збій пошти лише логується, бо перенесення вже збережено. Повертає кількість надісланих листів.
    """
    if not _semester_started():
        return 0

    emails = list(User.objects.filter(group=booking.lesson.group, is_active=True).values_list("email", flat=True))
    if not emails:
        return 0

    # Заголовок листа не може містити переноси рядків (назва дисципліни приходить із САЗ).
    subject = " ".join(f"UniSpace: змінено аудиторію для заняття «{booking.lesson.subject}»".split())
    body = generate_room_change_email_body(booking, previous_room, new_room)
    # Окремий лист кожному одержувачу, щоб студенти не бачили адрес одне одного.
    messages = tuple((subject, body, settings.DEFAULT_FROM_EMAIL, [email]) for email in emails)

    try:
        return send_mass_mail(messages)
    except OSError:  # smtplib.SMTPException і мережеві помилки/таймаути успадковують OSError
        logger.exception("Не вдалося надіслати email про зміну аудиторії (заняття %s)", booking.lesson_id)
        return 0
