from datetime import date, time

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from api.models import AcademicGroup, Booking, Lesson, Room, User


class Command(BaseCommand):
    help = "Create demo data for local UniSpace testing"

    def handle(self, *args, **options):
        # Do not allow demo data in production.
        if not settings.DEBUG:
            raise CommandError("Demo seed is only allowed when DEBUG=True")

        # Use a stable date for repeated runs.
        demo_date = date(2026, 11, 2)

        with transaction.atomic():

            # 1. Create academic groups
            group1, _ = AcademicGroup.objects.get_or_create(
                source_key="demo-group-1",
                defaults={"name": "ІПЗ-31"},
            )

            group2, _ = AcademicGroup.objects.get_or_create(
                source_key="demo-group-2",
                defaults={"name": "КБ-31"},
            )

            # 2. Create users
            teacher, _ = User.objects.get_or_create(
                email="demo.teacher@example.com",
                defaults={
                    "full_name": "Олена Коваль",
                    "role": User.RoleChoices.TEACHER,
                },
            )

            User.objects.get_or_create(
                email="demo.student@example.com",
                defaults={
                    "full_name": "Андрій Петренко",
                    "role": User.RoleChoices.STUDENT,
                    "group": group1,
                },
            )

            User.objects.get_or_create(
                email="demo.dispatcher@example.com",
                defaults={
                    "full_name": "Марія Шевченко",
                    "role": User.RoleChoices.DISPATCHER,
                },
            )

            # 3. Create rooms
            room_data = [
                ("1", "101", 30, True, False),
                ("1", "102", 50, True, True),
                ("2", "201", 20, False, True),
                ("2", "202", 80, True, True),
                ("3", "301", 40, False, False),
            ]

            rooms = []

            for building, number, capacity, projector, computers in room_data:
                room, _ = Room.objects.get_or_create(
                    building=building,
                    number=number,
                    defaults={
                        "capacity": capacity,
                        "projector_working": projector,
                        "has_computers": computers,
                        "is_available": True,
                    },
                )
                rooms.append(room)

            # 4. Create lessons and bookings
            lesson_data = [
                ("09:00", "10:30", "Програмна інженерія", group1, rooms[0]),
                ("11:00", "12:30", "Кібербезпека", group2, rooms[1]),
                ("13:00", "14:30", "Бази даних", group1, rooms[2]),
            ]

            for index, lesson_info in enumerate(lesson_data, start=1):
                start, end, subject, group, room = lesson_info

                start_hour, start_minute = map(int, start.split(":"))
                end_hour, end_minute = map(int, end.split(":"))

                lesson, _ = Lesson.objects.get_or_create(
                    source_key=f"demo-lesson-{index}",
                    defaults={
                        "subject": subject,
                        "date": demo_date,
                        "start_time": time(start_hour, start_minute),
                        "end_time": time(end_hour, end_minute),
                        "teacher": teacher,
                        "group": group,
                    },
                )

                Booking.objects.get_or_create(
                    lesson=lesson,
                    status=Booking.BookingStatus.ACTIVE,
                    defaults={
                        "room": room,
                        "user": teacher,
                        "source": Booking.BookingSource.MANUAL,
                    },
                )

        self.stdout.write(self.style.SUCCESS("Demo data created successfully!"))
