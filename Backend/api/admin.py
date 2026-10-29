"""
Налаштування Django-адмінки UniSpace для диспетчера.

Примітка щодо використання ШІ: цей модуль написано за допомогою ШІ (Claude)
Код перевірено людиною(Тимохина Ксенія).
"""

from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils import timezone

from .models import (
    AcademicGroup,
    AuditLog,
    Booking,
    Conflict,
    Lesson,
    Notification,
    Room,
    SyncLog,
    User,
)

# ==========================================
# Inline-блоки
# ==========================================


class BookingInline(admin.TabularInline):
    """Бронювання заняття: лише перегляд, бо час береться із заняття, а накладки контролює БД."""

    model = Booking
    fields = ("room", "status", "source", "start_time", "end_time")
    readonly_fields = ("room", "status", "source", "start_time", "end_time")
    extra = 0
    can_delete = False
    show_change_link = True

    def has_add_permission(self, request, obj=None):
        return False


class AuditLogInline(admin.TabularInline):
    """Історія дій над бронюванням. Журнал незмінний, тому лише перегляд."""

    model = AuditLog
    fields = ("created_at", "user", "action", "previous_room", "new_room", "reason")
    readonly_fields = fields
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


# ==========================================
# Користувачі та групи
# ==========================================


@admin.register(AcademicGroup)
class AcademicGroupAdmin(admin.ModelAdmin):
    """Реєструємо першим, бо на нього посилаються autocomplete_fields у UserAdmin і LessonAdmin."""

    list_display = ("name", "source_key")
    search_fields = ("name", "source_key")


class DispatcherCreationForm(forms.ModelForm):
    """Форма додавання користувача/диспетчера без пароля (для Microsoft SSO)."""

    class Meta:
        model = User
        fields = ("email", "full_name", "role", "group", "is_staff", "is_superuser")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_unusable_password()
        if user.role == User.RoleChoices.DISPATCHER:
            user.is_staff = True
        if commit:
            user.save()
        return user


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    add_form = DispatcherCreationForm
    form = forms.ModelForm

    list_display = ("email", "full_name", "role", "group", "is_staff", "is_active")
    list_filter = ("role", "is_staff", "is_superuser", "is_active", "group")
    search_fields = ("email", "full_name", "external_identity_id")
    list_select_related = ("group",)
    autocomplete_fields = ("group",)
    ordering = ("email",)
    readonly_fields = ("last_login", "date_joined")

    fieldsets = (
        (None, {"fields": ("email",)}),
        ("Персональні дані", {"fields": ("full_name", "role", "group", "external_identity_id")}),
        (
            "Права доступу",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Важливі дати", {"fields": ("last_login", "date_joined")}),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "full_name", "role", "group", "is_staff", "is_superuser"),
            },
        ),
    )

    def save_model(self, request, obj, form, change):
        if obj.role == User.RoleChoices.DISPATCHER:
            obj.is_staff = True
        super().save_model(request, obj, form, change)


# ==========================================
# Аудиторії, заняття та бронювання
# ==========================================


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ("number", "building", "capacity", "projector_working", "has_computers", "is_available")
    list_filter = ("building", "is_available", "projector_working", "has_computers")
    search_fields = ("number", "building", "board_type")
    list_editable = ("is_available",)


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ("subject", "date", "start_time", "end_time", "teacher", "group")
    list_filter = ("date", "group")
    search_fields = ("subject", "source_key", "teacher__email", "teacher__full_name", "group__name")
    list_select_related = ("teacher", "group")
    autocomplete_fields = ("teacher", "group")
    date_hierarchy = "date"
    inlines = [BookingInline]


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    """
    Бронювання. Час початку й кінця Booking.save() береться із заняття, тому поля лише для читання.

    Увага: накладку активних бронювань однієї аудиторії відхиляє ExclusionConstraint у PostgreSQL
    (IntegrityError), а адмінка цю помилку не перехоплює. Для зміни аудиторії краще користуватися API
    (POST /api/v1/bookings/{id}/change/), який пише AuditLog і сповіщає групу.
    """

    list_display = ("get_lesson_title", "room", "get_teacher", "start_time", "end_time", "status", "source")
    list_filter = ("status", "source", "room__building", "start_time")
    search_fields = (
        "lesson__subject",
        "room__number",
        "lesson__teacher__email",
        "lesson__teacher__full_name",
        "lesson__group__name",
    )
    list_select_related = ("lesson", "lesson__teacher", "room")
    autocomplete_fields = ("lesson", "room", "user")
    readonly_fields = ("start_time", "end_time", "created_at", "updated_at")
    date_hierarchy = "start_time"
    inlines = [AuditLogInline]

    @admin.display(description="Заняття", ordering="lesson__subject")
    def get_lesson_title(self, obj):
        return f"{obj.lesson.subject} ({obj.lesson.date})"

    @admin.display(description="Викладач", ordering="lesson__teacher__full_name")
    def get_teacher(self, obj):
        return obj.lesson.teacher


# ==========================================
# Конфлікти та сповіщення
# ==========================================


@admin.register(Conflict)
class ConflictAdmin(admin.ModelAdmin):
    list_display = ("room", "first_lesson", "second_lesson", "overlap_start", "overlap_end", "status", "detected_at")
    list_filter = ("status", "detected_at", "room__building")
    search_fields = ("room__number", "first_lesson__subject", "second_lesson__subject")
    list_select_related = ("room", "first_lesson", "second_lesson")
    autocomplete_fields = ("first_lesson", "second_lesson", "room")
    readonly_fields = ("detected_at",)
    date_hierarchy = "detected_at"
    actions = ["mark_resolved"]

    @admin.action(description="Позначити вибрані конфлікти вирішеними")
    def mark_resolved(self, request, queryset):
        updated = queryset.filter(status=Conflict.ConflictStatus.OPEN).update(
            status=Conflict.ConflictStatus.RESOLVED, resolved_at=timezone.now()
        )
        self.message_user(request, f"Вирішено конфліктів: {updated}.")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("user", "type", "is_read", "created_at")
    list_filter = ("is_read", "type", "created_at")
    search_fields = ("user__email", "user__full_name", "type", "message")
    list_select_related = ("user",)
    autocomplete_fields = ("user",)
    readonly_fields = ("created_at",)
    date_hierarchy = "created_at"


# ==========================================
# Журнали (лише перегляд)
# ==========================================


class ReadOnlyAdmin(admin.ModelAdmin):
    """Базовий клас для журналів: записи створює система, вручну їх не додають, не змінюють і не видаляють."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AuditLog)
class AuditLogAdmin(ReadOnlyAdmin):
    """AuditLog незмінний (AppendOnlyManager): видалення з адмінки викликало б ValidationError."""

    list_display = ("created_at", "action", "user", "booking", "previous_room", "new_room")
    list_filter = ("action", "created_at")
    search_fields = ("user__email", "booking__lesson__subject", "reason")
    list_select_related = ("user", "booking", "booking__lesson", "booking__room", "previous_room", "new_room")
    date_hierarchy = "created_at"


@admin.register(SyncLog)
class SyncLogAdmin(ReadOnlyAdmin):
    list_display = ("started_at", "finished_at", "status", "trigger")
    list_filter = ("status", "trigger", "started_at")
    search_fields = ("error_message",)
    date_hierarchy = "started_at"
