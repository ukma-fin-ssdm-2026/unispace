"""
Тести mock-ендпоінтів API (Lab05).

Перевіряють HTTP-коди (200/201/204/400/404) і єдиний формат помилок для пʼяти ендпоінтів.
Ендпоінти поки повертають заглушки й не працюють з базою даних, тому тести наслідують
APISimpleTestCase: тестова база не створюється, і тести однаково проходять на SQLite і PostgreSQL.
Коли зʼявляться моделі, тести на реальні дані треба буде перевести на APITestCase.

Примітка щодо використання ШІ: тести написано з допомогою ШІ (Claude) за кодом
api/views.py та api/serializers.py; перевірено запуском `python manage.py test` локально і в CI.

Контракт оновлено під TDD (використання UUID та lesson_id).
"""

import uuid
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from django.contrib.auth import get_user_model

User = get_user_model()

ERROR_KEYS = {"code", "message", "details", "request_id", "documentation"}


class ErrorFormatMixin:
    """Перевірка єдиного формату помилок API (docs/api/api-design.md)."""

    def assert_validation_error(self, response, *fields):
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        error = response.json()["error"]
        self.assertEqual(set(error), ERROR_KEYS)
        self.assertEqual(error["code"], "VALIDATION_ERROR")
        error_fields = {detail["field"] for detail in error["details"]}
        for field in fields:
            self.assertIn(field, error_fields)


class RoomListTests(ErrorFormatMixin, APITestCase):
    url = reverse("room-list")

    def test_list_rooms_returns_200(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.json(), list)

    def test_valid_filters_return_200(self):
        response = self.client.get(self.url, {"limit": 5, "offset": 0, "capacity": 30})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_limit_zero_returns_400(self):
        self.assert_validation_error(self.client.get(self.url, {"limit": 0}), "limit")

    def test_negative_offset_returns_400(self):
        self.assert_validation_error(self.client.get(self.url, {"offset": -1}), "offset")

    def test_non_numeric_capacity_returns_400(self):
        self.assert_validation_error(self.client.get(self.url, {"capacity": "abc"}), "capacity")


class AvailableSlotsTests(ErrorFormatMixin, APITestCase):
    url = reverse("available-slots")

    def setUp(self):
        self.test_room_id = str(uuid.uuid4())

    def test_valid_query_returns_200(self):
        response = self.client.get(self.url, {"room_id": self.test_room_id, "date": "2026-10-20"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_missing_params_returns_400(self):
        self.assert_validation_error(self.client.get(self.url), "room_id", "date")

    def test_invalid_uuid_format_returns_400(self):
        self.assert_validation_error(
            self.client.get(self.url, {"room_id": "not-a-uuid", "date": "2026-10-20"}), "room_id"
        )


class BookingCreateTests(ErrorFormatMixin, APITestCase):
    url = reverse("booking-list-create")

    def setUp(self):
        self.teacher = User.objects.create(email="teacher1@ukma.edu.ua", role="teacher")
        self.client.force_authenticate(user=self.teacher)

        self.valid_payload = {
            "room_id": str(uuid.uuid4()),
            "lesson_id": str(uuid.uuid4()),
        }

    def test_create_booking_returns_201(self):
        response = self.client.post(self.url, self.valid_payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_missing_lesson_id_returns_400(self):
        payload = {"room_id": self.valid_payload["room_id"]}
        self.assert_validation_error(self.client.post(self.url, payload, format="json"), "lesson_id")


class BookingDeleteTests(APITestCase):
    def setUp(self):
        self.dispatcher = User.objects.create(email="disp1@ukma.edu.ua", role="dispatcher")
        self.client.force_authenticate(user=self.dispatcher)

        self.test_booking_id = str(uuid.uuid4())
        self.unknown_booking_id = "00000000-0000-0000-0000-000000000000"

    def test_delete_existing_booking_returns_204(self):
        response = self.client.delete(reverse("booking-detail", args=[self.test_booking_id]))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_delete_unknown_booking_returns_404(self):
        response = self.client.delete(reverse("booking-detail", args=[self.unknown_booking_id]))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class UserBookingsTests(ErrorFormatMixin, APITestCase):
    url = reverse("user-bookings")

    def setUp(self):
        self.student = User.objects.create(email="student1@ukma.edu.ua", role="student")
        self.client.force_authenticate(user=self.student)

    def test_list_user_bookings_returns_200(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.json(), list)


class OpenApiSchemaTests(APITestCase):
    def test_schema_is_served(self):
        response = self.client.get(reverse("schema"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class BookingSecurityTests(APITestCase):
    """Regression tests for unauthorized operations."""

    def setUp(self):
        self.test_booking_id = str(uuid.uuid4())
        self.valid_payload = {
            "room_id": str(uuid.uuid4()),
            "lesson_id": str(uuid.uuid4()),
        }

    def test_anonymous_user_cannot_create_booking(self):
        response = self.client.post(reverse("booking-list-create"), self.valid_payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_anonymous_user_cannot_view_user_bookings(self):
        response = self.client.get(reverse("user-bookings"))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_student_cannot_create_booking(self):
        student = User.objects.create(email="student2@ukma.edu.ua", role="student")
        self.client.force_authenticate(user=student)
        response = self.client.post(reverse("booking-list-create"), self.valid_payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class SyncLogSecurityTests(APITestCase):
    """Перевірка доступу до логів синхронізації."""

    def setUp(self):
        self.student = User.objects.create(email="student3@ukma.edu.ua", role="student")
        self.dispatcher = User.objects.create(email="disp2@ukma.edu.ua", role="dispatcher")
        self.url = reverse("sync-log-list")

    def test_anonymous_cannot_view_sync_logs(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_student_cannot_view_sync_logs(self):
        self.client.force_authenticate(user=self.student)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_dispatcher_can_view_sync_logs(self):
        self.client.force_authenticate(user=self.dispatcher)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
