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

import re

from django.db.models import Q

from api.models import StudentDiscipline, User
from .booking_rules import is_recently_changed

LECTURE_STREAM_MARKER = "лекційний потік"
SPECIALTY_COURSE_RE = re.compile(r"^(.+?,\s*\d+\s*р\.н\.)", re.IGNORECASE)


# ==========================================
# Обмеження видимості розкладу
# ==========================================


def extract_specialty_course(group_name):
    """Витягує 'Спеціальність, X р.н.' із назви академічної групи."""
    if not group_name:
        return ""
    match = SPECIALTY_COURSE_RE.match(group_name.strip())
    return match.group(1).strip() if match else ""


def _subject_match_query(subject):
    """Збіг назви дисципліни з урахуванням можливих суфіксів у дужках."""
    return Q(subject__iexact=subject) | Q(subject__istartswith=f"{subject} (") | Q(subject__istartswith=f"{subject}(")


def _build_student_disciplines_filter(selected_disciplines):
    """Формує Q-фільтр для обраних студентом дисциплін (практична група + лекційний потік)."""
    combined_filter = Q()
    for subject, selected_group_id in selected_disciplines:
        group_match = Q(group_id=selected_group_id) | Q(group__name__icontains=LECTURE_STREAM_MARKER)
        combined_filter |= _subject_match_query(subject) & group_match
    return combined_filter


def limit_lessons_to_user(lessons, user, group_id):
    """
    Обмежує вибірку занять за роллю користувача (FR-006, FR-007).
    Студент бачить обов'язкові пари своєї групи/курсу + обрані дисципліни (вибіркові чи змінені групи),
    викладач - власні заняття, диспетчер - будь-які.
    """
    if user.role == User.RoleChoices.STUDENT:
        selected_disciplines = list(StudentDiscipline.objects.filter(user=user).values_list("subject", "group_id"))

        base_filter = Q()
        if user.group_id:
            base_filter = Q(group_id=user.group_id)
            specialty_course = extract_specialty_course(user.group.name)
            if specialty_course:
                base_filter |= Q(
                    group__name__istartswith=specialty_course,
                    group__name__icontains=LECTURE_STREAM_MARKER,
                )

        if not selected_disciplines:
            return lessons.filter(base_filter) if user.group_id else lessons.none()

        overridden_subjects = Q()
        for subject, _ in selected_disciplines:
            overridden_subjects |= _subject_match_query(subject)

        selected_filter = _build_student_disciplines_filter(selected_disciplines)
        if user.group_id:
            return lessons.filter((base_filter & ~overridden_subjects) | selected_filter)
        return lessons.filter(selected_filter)

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
