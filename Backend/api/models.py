"""
Цей модуль написано за допомогою ШІ.
ШІ використовувався для генерації коду Django-моделей (ORM) та обмежень бази даних
на основі попередньо спроєктованої логічної моделі команди, описаної у файлі data-model.md.
Увесь згенерований код верифіковано, перевірено на відповідність архітектурі проєкту
та стандартам безпеки команди.
"""

import uuid
from datetime import datetime

from django.contrib.auth.models import AbstractUser
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import DateTimeRangeField, RangeBoundary, RangeOperators

from django.core.exceptions import ValidationError
from django.conf import settings

from django.db import models
from django.db.models import F, Func, Q


class UUIDModel(models.Model):
    """Базова модель із UUID як первинним ключем."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class TsTzRange(Func):
    """Створює PostgreSQL-діапазон між двома часовими мітками."""

    function = "TSTZRANGE"
    output_field = DateTimeRangeField()


class User(AbstractUser):
    """Користувач UniSpace."""

    class RoleChoices(models.TextChoices):
        STUDENT = "student", "Студент"
        TEACHER = "teacher", "Викладач"
        DISPATCHER = "dispatcher", "Диспетчер"

    username = None
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    external_identity_id = models.CharField(
        "Зовнішній ID Microsoft", max_length=255, unique=True, null=True, blank=True
    )
    email = models.EmailField("Університетська електронна пошта", unique=True)
    full_name = models.CharField("Повне ім'я", max_length=255, blank=True, default="")
    role = models.CharField("Роль", max_length=15, choices=RoleChoices.choices, default=RoleChoices.STUDENT)
    group = models.ForeignKey(
        "AcademicGroup",
        on_delete=models.SET_NULL,
        verbose_name="Академічна група",
        related_name="users",
        null=True,
        blank=True,
    )

    # TODO (модель): Уточнити, який стабільний ідентифікатор Microsoft
    # зберігатиметься в external_identity_id.
    # TODO (модель): Перевірити, чи потрібні додаткові поля профілю
    # відповідно до остаточних вимог системи.

    class Meta:
        verbose_name = "Користувач"
        verbose_name_plural = "Користувачі"
        ordering = ["email"]

    def __str__(self):
        return self.full_name or self.email


class AcademicGroup(UUIDModel):
    """Академічна група."""

    name = models.CharField("Назва групи", max_length=100)
    source_key = models.CharField("Зовнішній ключ САЗ", max_length=255, unique=True)

    # TODO (модель): Перевірити формат і стабільність зовнішнього ключа
    # групи відповідно до фактичної структури даних САЗ.

    class Meta:
        verbose_name = "Академічна група"
        verbose_name_plural = "Академічні групи"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Lesson(UUIDModel):
    """Заняття."""

    source_key = models.CharField("Зовнішній ключ САЗ", max_length=255, unique=True)
    subject = models.CharField("Назва дисципліни", max_length=255)
    date = models.DateField("Дата заняття")
    start_time = models.TimeField("Час початку")
    end_time = models.TimeField("Час завершення")
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, verbose_name="Викладач", related_name="lessons_taught"
    )
    group = models.ForeignKey(
        AcademicGroup, on_delete=models.PROTECT, verbose_name="Академічна група", related_name="lessons"
    )

    # TODO (модель): Перевірити, чи достатньо source_key для стабільної
    # ідентифікації заняття між різними імпортами САЗ.

    class Meta:
        verbose_name = "Заняття"
        verbose_name_plural = "Заняття"
        ordering = ["date", "start_time", "subject"]
        constraints = [
            models.CheckConstraint(condition=Q(start_time__lt=F("end_time")), name="lesson_start_before_end"),
        ]
        indexes = [
            models.Index(fields=["date", "start_time"], name="lesson_date_start_idx"),
            models.Index(fields=["teacher", "date"], name="lesson_teacher_date_idx"),
        ]

    def __str__(self):
        return f"{self.subject} — {self.date} ({self.group.name})"


class Room(UUIDModel):
    """Аудиторія університету."""

    building = models.CharField("Корпус", max_length=20)
    number = models.CharField("Номер аудиторії", max_length=30)
    capacity = models.PositiveIntegerField("Місткість")
    board_type = models.CharField("Тип дошки", max_length=50, blank=True, default="")
    projector_working = models.BooleanField("Справний проєктор", default=False)
    has_computers = models.BooleanField("Наявність комп'ютерів", default=False)
    is_available = models.BooleanField("Доступна для використання", default=True)

    class Meta:
        verbose_name = "Аудиторія"
        verbose_name_plural = "Аудиторії"
        ordering = ["building", "number"]
        constraints = [
            models.UniqueConstraint(fields=["building", "number"], name="uniq_room_building_number"),
            models.CheckConstraint(condition=Q(capacity__gte=1), name="room_capacity_positive"),
        ]

    def __str__(self):
        return f"{self.number} (корпус {self.building}, {self.capacity} місць)"


class Booking(UUIDModel):
    """Призначення аудиторії для заняття."""

    class BookingStatus(models.TextChoices):
        ACTIVE = "active", "Активне"
        CANCELLED = "cancelled", "Скасоване"

    class BookingSource(models.TextChoices):
        SAZ = "saz", "Імпорт із САЗ"
        MANUAL = "manual", "Створене вручну"

    lesson = models.ForeignKey(Lesson, on_delete=models.PROTECT, verbose_name="Заняття", related_name="bookings")
    room = models.ForeignKey(Room, on_delete=models.PROTECT, verbose_name="Аудиторія", related_name="bookings")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        verbose_name="Автор бронювання",
        related_name="bookings",
        null=True,
        blank=True,
    )
    start_time = models.DateTimeField("Час початку")
    end_time = models.DateTimeField("Час завершення")
    status = models.CharField("Статус", max_length=15, choices=BookingStatus.choices, default=BookingStatus.ACTIVE)
    source = models.CharField(
        "Джерело бронювання", max_length=10, choices=BookingSource.choices, default=BookingSource.MANUAL
    )
    created_at = models.DateTimeField("Дата створення", auto_now_add=True)
    updated_at = models.DateTimeField("Дата оновлення", auto_now=True)

    # Часові поля зберігаються окремо для перевірки перетинів на рівні БД.

    class Meta:
        verbose_name = "Бронювання"
        verbose_name_plural = "Бронювання"
        ordering = ["-start_time"]
        constraints = [
            models.CheckConstraint(condition=Q(start_time__lt=F("end_time")), name="booking_start_before_end"),
            models.UniqueConstraint(
                fields=["lesson"], condition=Q(status="active"), name="uniq_active_booking_per_lesson"
            ),
            ExclusionConstraint(
                name="booking_active_room_time_excl",
                expressions=[
                    (TsTzRange("start_time", "end_time", RangeBoundary()), RangeOperators.OVERLAPS),
                    ("room", RangeOperators.EQUAL),
                ],
                condition=Q(status="active"),
                violation_error_message="Аудиторія вже заброньована на цей час.",
            ),
        ]
        indexes = [
            models.Index(fields=["room", "status", "start_time"], name="booking_room_status_start_idx"),
            models.Index(fields=["user", "start_time"], name="booking_user_start_idx"),
        ]

    # Автоматично синхронізуємо час бронювання з часом заняття перед збереженням
    def save(self, *args, **kwargs):
        if hasattr(self, "lesson") and self.lesson:
            self.start_time = datetime.combine(self.lesson.date, self.lesson.start_time)
            self.end_time = datetime.combine(self.lesson.date, self.lesson.end_time)
        super().save(*args, **kwargs)

    def __str__(self):
        subject = self.lesson.subject if hasattr(self, "lesson") and self.lesson else "Невідоме заняття"
        if self.start_time:
            return f"{subject} | {self.room} ({self.start_time:%d.%m.%Y %H:%M})"
        return f"{subject} | {self.room}"


class Conflict(UUIDModel):
    """Зареєстрований конфлікт між двома заняттями."""

    class ConflictStatus(models.TextChoices):
        OPEN = "open", "Відкритий"
        RESOLVED = "resolved", "Вирішений"

    first_lesson = models.ForeignKey(
        Lesson, on_delete=models.PROTECT, verbose_name="Перше заняття", related_name="conflicts_as_first"
    )
    second_lesson = models.ForeignKey(
        Lesson, on_delete=models.PROTECT, verbose_name="Друге заняття", related_name="conflicts_as_second"
    )
    room = models.ForeignKey(Room, on_delete=models.PROTECT, verbose_name="Аудиторія", related_name="conflicts")
    overlap_start = models.DateTimeField("Початок перетину")
    overlap_end = models.DateTimeField("Кінець перетину")
    detected_at = models.DateTimeField("Час виявлення", auto_now_add=True)
    status = models.CharField(
        "Статус конфлікту", max_length=10, choices=ConflictStatus.choices, default=ConflictStatus.OPEN
    )
    resolved_at = models.DateTimeField("Час розв'язання", null=True, blank=True)

    # TODO (модель): Уточнити, чи потрібно зберігати додаткові дані
    # для розрізнення повторно виявлених конфліктів.

    class Meta:
        verbose_name = "Конфлікт"
        verbose_name_plural = "Конфлікти"
        ordering = ["-detected_at"]
        constraints = [
            models.CheckConstraint(condition=Q(overlap_start__lt=F("overlap_end")), name="conflict_start_before_end"),
            models.CheckConstraint(condition=~Q(first_lesson=F("second_lesson")), name="conflict_lessons_different"),
        ]

    def __str__(self):
        return f"Конфлікт у {self.room}: {self.status}"


class Notification(UUIDModel):
    """Внутрішнє сповіщення користувача."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="Отримувач", related_name="notifications"
    )
    type = models.CharField("Тип сповіщення", max_length=50)
    message = models.TextField("Текст сповіщення")
    created_at = models.DateTimeField("Дата створення", auto_now_add=True)
    is_read = models.BooleanField("Прочитано", default=False)

    class Meta:
        verbose_name = "Сповіщення"
        verbose_name_plural = "Сповіщення"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "is_read", "created_at"], name="notification_user_read_idx"),
        ]

    def __str__(self):
        return f"{self.user} — {self.type}"


class AppendOnlyQuerySet(models.QuerySet):
    """Забороняє змінювати або видаляти записи через QuerySet."""

    def update(self, **kwargs):
        raise ValidationError("Записи AuditLog не можна змінювати.")

    def delete(self):
        raise ValidationError("Записи AuditLog не можна видаляти.")


class AppendOnlyManager(models.Manager.from_queryset(AppendOnlyQuerySet)):
    """Менеджер для незмінних записів аудиту."""


class AuditLog(UUIDModel):
    """Історія дій над бронюваннями."""

    booking = models.ForeignKey(Booking, on_delete=models.PROTECT, verbose_name="Бронювання", related_name="audit_logs")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, verbose_name="Автор дії", related_name="audit_logs"
    )
    action = models.CharField("Дія", max_length=50)
    previous_room = models.ForeignKey(
        Room,
        on_delete=models.PROTECT,
        verbose_name="Попередня аудиторія",
        related_name="audit_logs_as_previous_room",
        null=True,
        blank=True,
    )
    new_room = models.ForeignKey(
        Room,
        on_delete=models.PROTECT,
        verbose_name="Нова аудиторія",
        related_name="audit_logs_as_new_room",
        null=True,
        blank=True,
    )
    reason = models.TextField("Причина", blank=True, default="")
    created_at = models.DateTimeField("Дата дії", auto_now_add=True)

    objects = AppendOnlyManager()

    # TODO (БД): Захистити записи від зміни й видалення на рівні PostgreSQL.
    # Менеджер і перевизначені методи Django самі по собі не забезпечують
    # повної незмінності журналу.
    # TODO (БД): Забезпечити зберігання записів щонайменше 12 місяців.

    class Meta:
        verbose_name = "Запис аудиту"
        verbose_name_plural = "Журнал аудиту"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["booking", "created_at"], name="audit_booking_created_idx"),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Наявні записи AuditLog не можна змінювати.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Записи AuditLog не можна видаляти.")

    def __str__(self):
        return f"{self.action} — {self.created_at:%d.%m.%Y %H:%M}"


class SyncLog(UUIDModel):
    """Журнал результатів спроб синхронізації розкладу із САЗ."""

    class SyncStatus(models.TextChoices):
        SUCCESS = "success", "Успішно"
        FAILED = "failed", "Помилка"

    started_at = models.DateTimeField("Час початку", auto_now_add=True)
    finished_at = models.DateTimeField("Час завершення", null=True, blank=True)
    status = models.CharField("Статус синхронізації", max_length=10, choices=SyncStatus.choices)
    error_message = models.TextField("Повідомлення про помилку", blank=True, default="")

    class Meta:
        verbose_name = "Журнал синхронізації"
        verbose_name_plural = "Журнал синхронізацій"
        ordering = ["-started_at"]

    def __str__(self):
        return f"Синхронізація {self.started_at:%d.%m.%Y %H:%M} — {self.status}"
