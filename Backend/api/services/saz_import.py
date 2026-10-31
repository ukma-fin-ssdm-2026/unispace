"""
Імпорт розкладу САЗ у базу UniSpace (FR-004, FR-005, FR-013, REL-002).

Отримує результат saz_parser.parse_schedule і:
- створює академічні групи (окремо лекційний потік і практичні групи) та викладачів;
- розгортає кожен рядок розкладу на заняття за тижнями семестру (дата = понеділок 1-го тижня + тиждень + день);
- для занять в аудиторіях із довідника створює бронювання за замовчуванням (source = saz);
- якщо аудиторія на цей час уже зайнята, записує Conflict замість бронювання (FR-013).

Повторний імпорт того самого розкладу нічого не дублює: заняття шукаються за source_key, а наявне активне
бронювання заняття не змінюється (зокрема, якщо викладач уже переніс заняття в іншу аудиторію).
Увесь імпорт виконується однією транзакцією: якщо щось пішло не так, попередні дані лишаються (REL-002).

Примітка щодо використання ШІ: модуль згенеровано ШІ (Claude); поведінку перевіряють тести test_saz_import.py.
"""

import hashlib
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from api.models import AcademicGroup, Booking, Conflict, Lesson, Room, User

from .saz_parser import LECTURE

PLACEHOLDER_EMAIL_DOMAIN = "saz.invalid"


@dataclass
class ImportResult:
    lessons_created: int = 0
    lessons_updated: int = 0
    bookings_created: int = 0
    conflicts_created: int = 0
    teachers_created: int = 0
    online_lessons: int = 0
    warnings: list = field(default_factory=list)

    def as_dict(self):
        return {
            "lessons_created": self.lessons_created,
            "lessons_updated": self.lessons_updated,
            "bookings_created": self.bookings_created,
            "conflicts_created": self.conflicts_created,
            "teachers_created": self.teachers_created,
            "online_lessons": self.online_lessons,
            "warnings": list(self.warnings),
        }


def _digest(*parts):
    """Короткий стабільний ключ для source_key (не для безпеки). SHA-256, бо SHA-1 bandit і Sonar вважають слабким."""
    return hashlib.sha256("|".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:16]


def _group(schedule, group_label):
    base = f"{schedule.specialty}, {schedule.year} р.н."
    name = f"{base} (лекційний потік)" if group_label == LECTURE else f"{base}, група {group_label}"
    group, _ = AcademicGroup.objects.get_or_create(
        source_key=f"saz:group:{_digest(schedule.specialty, schedule.year, group_label)}",
        defaults={"name": name[:100]},
    )
    return group


def _teacher(name, result, cache):
    """
    Викладач за ПІБ із САЗ. Пошти в САЗ немає, тож нового викладача створено з тимчасовою адресою
    @saz.invalid; зв'язати його з входом через Microsoft має диспетчер (відкрите питання data-model.md).
    """
    if name in cache:
        return cache[name]
    teacher = User.objects.filter(role=User.RoleChoices.TEACHER, full_name=name).first()
    if teacher is None:
        teacher = User(
            email=f"saz-teacher-{_digest(name)}@{PLACEHOLDER_EMAIL_DOMAIN}",
            full_name=name,
            role=User.RoleChoices.TEACHER,
        )
        teacher.set_unusable_password()
        teacher.save()
        result.teachers_created += 1
    cache[name] = teacher
    return teacher


def _room(entry, cache):
    """Аудиторія з довідника за корпусом і номером; номер у довіднику може бути «223» або «1-223»."""
    if entry.room not in cache:
        building, number = entry.room
        cache[entry.room] = Room.objects.filter(building=building, number__in=[number, f"{building}-{number}"]).first()
    return cache[entry.room]


def _book_or_record_conflict(lesson, room, result):
    if lesson.bookings.filter(status=Booking.BookingStatus.ACTIVE).exists():
        return  # бронювання вже є (з попереднього імпорту або змінене викладачем) - не чіпаємо
    try:
        with transaction.atomic():
            Booking.objects.create(lesson=lesson, room=room, source=Booking.BookingSource.SAZ)
        result.bookings_created += 1
        return
    except IntegrityError:
        pass

    # Бронювання не створилось: або аудиторія зайнята на цей час (ExclusionConstraint), або інше обмеження.
    start = timezone.make_aware(datetime.combine(lesson.date, lesson.start_time))
    end = timezone.make_aware(datetime.combine(lesson.date, lesson.end_time))
    other = (
        Booking.objects.filter(room=room, status=Booking.BookingStatus.ACTIVE, start_time__lt=end, end_time__gt=start)
        .exclude(lesson=lesson)
        .select_related("lesson")
        .first()
    )
    if other is None:
        return
    _, created = Conflict.objects.get_or_create(
        first_lesson=other.lesson,
        second_lesson=lesson,
        room=room,
        defaults={"overlap_start": max(start, other.start_time), "overlap_end": min(end, other.end_time)},
    )
    if created:
        result.conflicts_created += 1


def import_schedule(schedule, semester_start: date):
    """Імпортує розклад; semester_start - будь-який день першого навчального тижня семестру."""
    week_one_monday = semester_start - timedelta(days=semester_start.weekday())
    result = ImportResult(warnings=list(schedule.warnings))
    teachers, rooms = {}, {}
    unknown_rooms = set()

    with transaction.atomic():
        for entry in schedule.entries:
            group = _group(schedule, entry.group)
            teacher = _teacher(entry.teacher or "Викладач не вказаний", result, teachers)
            room = _room(entry, rooms) if entry.room else None
            if room is None and not entry.online_only:
                # «1-225» і «1-225 /онлайн» - та сама аудиторія, тож у попередженні вона одна
                unknown_rooms.add("-".join(entry.room) if entry.room else entry.room_raw)
            if entry.online_only:
                result.online_lessons += len(entry.weeks)

            for week in entry.weeks:
                lesson_date = week_one_monday + timedelta(weeks=week - 1, days=entry.weekday)
                key = "saz:lesson:" + _digest(
                    schedule.specialty,
                    schedule.year,
                    entry.group,
                    lesson_date,
                    entry.start,
                    entry.subject,
                    entry.teacher,
                )
                lesson, created = Lesson.objects.update_or_create(
                    source_key=key,
                    defaults={
                        "subject": entry.subject[:255],
                        "date": lesson_date,
                        "start_time": entry.start,
                        "end_time": entry.end,
                        "teacher": teacher,
                        "group": group,
                    },
                )
                if created:
                    result.lessons_created += 1
                else:
                    result.lessons_updated += 1
                if room is not None:
                    _book_or_record_conflict(lesson, room, result)

    for raw in sorted(unknown_rooms):
        result.warnings.append(f"Аудиторію «{raw}» не знайдено в довіднику: заняття імпортовано без бронювання")
    return result


def run_sync(html, semester_start: date, trigger=None):
    """
    Одна спроба синхронізації (FR-005): журнал SyncLog in_progress -> success / failed.
    Помилка розбору чи імпорту не змінює вже імпортовані дані (REL-002) і записується в журнал.
    Повертає (sync_log, ImportResult або None).
    """
    from api.models import SyncLog

    from .saz_parser import SazParseError, parse_schedule

    log = SyncLog.objects.create(
        status=SyncLog.SyncStatus.IN_PROGRESS,
        trigger=trigger or SyncLog.SyncTrigger.MANUAL,
    )
    try:
        result = import_schedule(parse_schedule(html), semester_start)
    except (SazParseError, ValueError) as error:
        log.status = SyncLog.SyncStatus.FAILED
        log.error_message = str(error)
        result = None
    else:
        log.status = SyncLog.SyncStatus.SUCCESS
    log.finished_at = timezone.now()
    log.save(update_fields=["status", "error_message", "finished_at"])
    return log, result
