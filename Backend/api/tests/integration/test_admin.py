"""
Тести безпеки та обмежень Django-адмінки UniSpace (SEC-001).

Перевіряють захист акаунта суперюзера, заборону ескалації прав для диспетчера,
автоматичну синхронізацію is_staff із роллю, режим лише для читання для
системних моделей (Lesson, Booking, Notification, AuditLog, SyncLog) та
обробку статусів у ConflictAdmin.

Примітка щодо використання ШІ: тести написано з допомогою ШІ (Gemini) за SEC-001;
запуск `pytest` локально і в CI виконує автор PR.
"""

from datetime import date, time, timedelta

import pytest
from django.contrib.admin.sites import AdminSite
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory
from django.utils import timezone

from api.admin import (
    AcademicGroupAdmin,
    AuditLogAdmin,
    BookingAdmin,
    ConflictAdmin,
    DispatcherCreationForm,
    LessonAdmin,
    NotificationAdmin,
    SyncLogAdmin,
    UserAdmin,
    AuditLogInline,
    BookingInline,
)
from api.models import (
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

pytestmark = [pytest.mark.django_db, pytest.mark.req("SEC-001")]


# ==========================================
# Фікстури та Хелпери
# ==========================================


@pytest.fixture
def site():
    return AdminSite()


@pytest.fixture
def rf():
    return RequestFactory()


def _make_request(rf, user):
    """Створює запит із користувачем та підтримкою Django messages (для admin actions)."""
    request = rf.get("/admin/")
    request.user = user
    request.session = {}
    request._messages = FallbackStorage(request)
    return request


@pytest.fixture
def superuser():
    return User.objects.create(
        email="root@ukma.edu.ua",
        full_name="Головний Адмін",
        role=User.RoleChoices.DISPATCHER,
        is_staff=True,
        is_superuser=True,
    )


@pytest.fixture
def dispatcher():
    return User.objects.create(
        email="dispatcher@ukma.edu.ua",
        full_name="Диспетчер Розкладу",
        role=User.RoleChoices.DISPATCHER,
        is_staff=True,
        is_superuser=False,
    )


@pytest.fixture
def student():
    return User.objects.create(
        email="student@ukma.edu.ua",
        full_name="Студент Тестовий",
        role=User.RoleChoices.STUDENT,
        is_staff=False,
        is_superuser=False,
    )


@pytest.fixture
def open_conflict(student):
    group = AcademicGroup.objects.create(name="ІПЗ-3", source_key="grp-ipz-3")
    room = Room.objects.create(number="101", building="1", capacity=30)
    lesson1 = Lesson.objects.create(
        subject="Алгоритми",
        date=date(2026, 11, 20),
        start_time=time(10, 0),
        end_time=time(11, 20),
        teacher=student,
        group=group,
        source_key="lesson-1",
    )
    lesson2 = Lesson.objects.create(
        subject="Бази даних",
        date=date(2026, 11, 20),
        start_time=time(10, 0),
        end_time=time(11, 20),
        teacher=student,
        group=group,
        source_key="lesson-2",
    )
    now = timezone.now()
    return Conflict.objects.create(
        room=room,
        first_lesson=lesson1,
        second_lesson=lesson2,
        overlap_start=now,
        overlap_end=now + timedelta(hours=1),
        status=Conflict.ConflictStatus.OPEN,
    )

    # ==========================================
    # UserAdmin та DispatcherCreationForm
    # ==========================================


def test_dispatcher_cannot_escalate_privileges_via_readonly_fields(site, rf, dispatcher, student):
    model_admin = UserAdmin(User, site)
    request = _make_request(rf, dispatcher)

    readonly = model_admin.get_readonly_fields(request, obj=student)

    for field in ("external_identity_id", "is_staff", "is_superuser", "groups", "user_permissions"):
        assert field in readonly


def test_dispatcher_sees_superuser_core_fields_as_readonly(site, rf, dispatcher, superuser):
    model_admin = UserAdmin(User, site)
    request = _make_request(rf, dispatcher)

    readonly = model_admin.get_readonly_fields(request, obj=superuser)

    for field in ("email", "role", "is_active", "is_staff", "is_superuser"):
        assert field in readonly


def test_superuser_can_edit_permission_fields(site, rf, superuser, student):
    model_admin = UserAdmin(User, site)
    request = _make_request(rf, superuser)

    readonly = model_admin.get_readonly_fields(request, obj=student)

    assert "external_identity_id" in readonly
    assert "is_staff" not in readonly
    assert "is_superuser" not in readonly


def test_dispatcher_cannot_change_or_delete_superuser(site, rf, dispatcher, superuser):
    model_admin = UserAdmin(User, site)
    request = _make_request(rf, dispatcher)

    assert model_admin.has_change_permission(request, obj=superuser) is False
    assert model_admin.has_delete_permission(request, obj=superuser) is False


def test_superuser_can_change_and_delete_superuser(site, rf, superuser):
    model_admin = UserAdmin(User, site)
    request = _make_request(rf, superuser)

    assert model_admin.has_change_permission(request, obj=superuser) is True
    assert model_admin.has_delete_permission(request, obj=superuser) is True


def test_dispatcher_bulk_delete_skips_superuser(site, rf, dispatcher, superuser, student):
    model_admin = UserAdmin(User, site)
    request = _make_request(rf, dispatcher)
    qs = User.objects.filter(pk__in=[superuser.pk, student.pk])

    model_admin.delete_queryset(request, qs)

    assert User.objects.filter(pk=superuser.pk).exists() is True
    assert User.objects.filter(pk=student.pk).exists() is False


def test_save_model_syncs_is_staff_with_dispatcher_role(site, rf, dispatcher, student):
    model_admin = UserAdmin(User, site)
    request = _make_request(rf, dispatcher)

    student.role = User.RoleChoices.DISPATCHER
    model_admin.save_model(request, student, form=None, change=True)
    student.refresh_from_db()
    assert student.is_staff is True

    student.role = User.RoleChoices.STUDENT
    model_admin.save_model(request, student, form=None, change=True)
    student.refresh_from_db()
    assert student.is_staff is False


def test_save_model_does_not_strip_is_staff_from_superuser(site, rf, superuser):
    model_admin = UserAdmin(User, site)
    request = _make_request(rf, superuser)

    superuser.role = User.RoleChoices.STUDENT
    model_admin.save_model(request, superuser, form=None, change=True)
    superuser.refresh_from_db()

    assert superuser.is_staff is True


def test_dispatcher_creation_form_sets_unusable_password_and_staff():
    form = DispatcherCreationForm(
        data={
            "email": "new.dispatcher@ukma.edu.ua",
            "full_name": "Новий Диспетчер",
            "role": User.RoleChoices.DISPATCHER,
        }
    )
    assert form.is_valid(), form.errors

    user = form.save()

    assert user.has_usable_password() is False
    assert user.is_staff is True
    assert user.is_superuser is False

    # ==========================================
    # ReadOnlyAdmin та системні моделі
    # ==========================================


@pytest.mark.parametrize(
    ("model", "admin_cls"),
    [
        (Lesson, LessonAdmin),
        (Booking, BookingAdmin),
        (Notification, NotificationAdmin),
        (AuditLog, AuditLogAdmin),
        (SyncLog, SyncLogAdmin),
    ],
)
def test_system_models_are_strictly_read_only(site, rf, superuser, model, admin_cls):
    model_admin = admin_cls(model, site)
    request = _make_request(rf, superuser)

    assert model_admin.has_add_permission(request) is False
    assert model_admin.has_change_permission(request) is False
    assert model_admin.has_delete_permission(request) is False


def test_academic_group_admin_forbids_manual_add(site, rf, superuser):
    model_admin = AcademicGroupAdmin(AcademicGroup, site)
    request = _make_request(rf, superuser)

    assert model_admin.has_add_permission(request) is False

    # ==========================================
    # ConflictAdmin
    # ==========================================


def test_conflict_admin_forbids_add_and_delete(site, rf, superuser, open_conflict):
    model_admin = ConflictAdmin(Conflict, site)
    request = _make_request(rf, superuser)

    assert model_admin.has_add_permission(request) is False
    assert model_admin.has_delete_permission(request, obj=open_conflict) is False


def test_conflict_admin_save_model_manages_resolved_at(site, rf, dispatcher, open_conflict):
    model_admin = ConflictAdmin(Conflict, site)
    request = _make_request(rf, dispatcher)

    open_conflict.status = Conflict.ConflictStatus.RESOLVED
    model_admin.save_model(request, open_conflict, form=None, change=True)
    open_conflict.refresh_from_db()
    assert open_conflict.resolved_at is not None

    # Повторне збереження вже вирішеного конфлікту не перезаписує resolved_at
    first_resolved_at = open_conflict.resolved_at
    model_admin.save_model(request, open_conflict, form=None, change=True)
    open_conflict.refresh_from_db()
    assert open_conflict.resolved_at == first_resolved_at

    open_conflict.status = Conflict.ConflictStatus.OPEN
    model_admin.save_model(request, open_conflict, form=None, change=True)
    open_conflict.refresh_from_db()
    assert open_conflict.resolved_at is None


def test_conflict_admin_mark_resolved_action(site, rf, dispatcher, open_conflict):
    model_admin = ConflictAdmin(Conflict, site)
    request = _make_request(rf, dispatcher)

    model_admin.mark_resolved(request, Conflict.objects.filter(pk=open_conflict.pk))
    open_conflict.refresh_from_db()

    assert open_conflict.status == Conflict.ConflictStatus.RESOLVED
    assert open_conflict.resolved_at is not None

    # ==========================================
    # Інлайни, відображення та додаткові гілки
    # ==========================================


def test_dispatcher_creation_form_for_student_keeps_is_staff_false():
    form = DispatcherCreationForm(
        data={
            "email": "new.student@ukma.edu.ua",
            "full_name": "Новий Студент",
            "role": User.RoleChoices.STUDENT,
        }
    )
    assert form.is_valid(), form.errors

    user = form.save(commit=False)

    assert user.has_usable_password() is False
    assert user.is_staff is False


def test_superuser_bulk_delete_can_delete_users(site, rf, superuser, student):
    model_admin = UserAdmin(User, site)
    request = _make_request(rf, superuser)
    qs = User.objects.filter(pk=student.pk)

    model_admin.delete_queryset(request, qs)

    assert User.objects.filter(pk=student.pk).exists() is False


def test_inlines_are_read_only(site, rf, superuser):
    request = _make_request(rf, superuser)

    booking_inline = BookingInline(Lesson, site)
    assert booking_inline.has_add_permission(request) is False

    audit_inline = AuditLogInline(Booking, site)
    assert audit_inline.has_add_permission(request) is False
    assert audit_inline.has_change_permission(request) is False


def test_booking_admin_display_helpers(site, open_conflict):
    model_admin = BookingAdmin(Booking, site)
    booking = Booking(lesson=open_conflict.first_lesson, room=open_conflict.room)

    assert (
        model_admin.get_lesson_title(booking)
        == f"{open_conflict.first_lesson.subject} ({open_conflict.first_lesson.date})"
    )
    assert model_admin.get_teacher(booking) == open_conflict.first_lesson.teacher
