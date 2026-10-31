"""
Сервіс формування розкладу для API.
Містить логіку маппінгу занять та обмеження видимості розкладу за ролями.

Архітектурне рішення: Чому цей файл відокремлено від `scheduling.py`?
Цей модуль (`schedule.py`) працює з базою даних, моделями Django (User, Lesson)
та бізнес-логікою застосунку (Application Layer). Він знає про структуру бази
і готує словники для серіалізаторів API. Натомість `scheduling.py` відповідає
виключно за математичні розрахунки часу і повністю ізольований від бази даних.

Примітка щодо використання ШІ: код винесено з views.py за допомогою ШІ-асистента.
"""

from api.models import User
from .booking_rules import is_recently_changed

# ==========================================
# Обмеження видимості розкладу
# ==========================================


def limit_lessons_to_user(lessons, user, group_id):
    """Студент бачить розклад своєї групи, викладач - власні заняття, диспетчер - будь-які (FR-006, FR-007)."""
    if user.role == User.RoleChoices.STUDENT:
        return lessons.filter(group_id=user.group_id)
    if user.role == User.RoleChoices.TEACHER:
        return lessons.filter(teacher=user)
    if group_id:
        return lessons.filter(group_id=group_id)
    return lessons

    # ==========================================
    # Формування даних (Маппінг)
    # ==========================================


def build_schedule_item(lesson):
    """Мапить об'єкт Lesson у словник для ScheduleItemSerializer."""
    booking = lesson.active_bookings[0] if lesson.active_bookings else None
    room = booking.room if booking else None
    room_changed = False

    if booking:
        change_times = [change.created_at for change in booking.room_changes]
        room_changed = is_recently_changed(change_times, booking.start_time)

    return {
        "lesson_id": lesson.id,
        "booking_id": booking.id if booking else None,
        "subject": lesson.subject,
        "date": lesson.date,
        "start_time": lesson.start_time,
        "end_time": lesson.end_time,
        "group": lesson.group.name,
        "teacher": str(lesson.teacher),
        "room": room,
        "room_assigned": room is not None,
        "room_changed": room_changed,
    }
