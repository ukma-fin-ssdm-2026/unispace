import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

from api.models import AcademicGroup, Booking, Lesson, Room, User


def get_demo_bookings():
    demo_lessons = Lesson.objects.filter(source_key__startswith="demo-lesson-")
    return Booking.objects.filter(lesson__in=demo_lessons)


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_seed_demo_creates_data():
    call_command("seed_demo")

    groups_count = AcademicGroup.objects.filter(source_key__startswith="demo-").count()
    users_count = User.objects.filter(email__startswith="demo.").count()
    rooms_count = Room.objects.filter(building__in=["1", "2", "3"]).count()
    lessons_count = Lesson.objects.filter(source_key__startswith="demo-lesson-").count()
    bookings_count = get_demo_bookings().count()

    assert groups_count == 2
    assert users_count == 3
    assert rooms_count == 5
    assert lessons_count == 3
    assert bookings_count == 3


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_seed_demo_is_idempotent():
    call_command("seed_demo")

    first_count = get_demo_bookings().count()

    call_command("seed_demo")

    second_count = get_demo_bookings().count()

    assert first_count == 3
    assert second_count == first_count


@pytest.mark.django_db
@override_settings(DEBUG=False)
def test_seed_demo_blocked_in_production():
    with pytest.raises(CommandError):
        call_command("seed_demo")
