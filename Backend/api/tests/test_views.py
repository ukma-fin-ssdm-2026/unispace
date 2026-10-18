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
from unittest.mock import Mock
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APISimpleTestCase

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


class RoomListTests(ErrorFormatMixin, APISimpleTestCase):
    url = reverse("room-list")

    def test_list_rooms_returns_200(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.json(), list)
        self.assertEqual(set(response.json()[0]), {"id", "name", "capacity", "has_projector"})

    def test_valid_filters_return_200(self):
        response = self.client.get(self.url, {"limit": 5, "offset": 0, "capacity": 30})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_limit_zero_returns_400(self):
        self.assert_validation_error(self.client.get(self.url, {"limit": 0}), "limit")

    def test_negative_offset_returns_400(self):
        self.assert_validation_error(self.client.get(self.url, {"offset": -1}), "offset")

    def test_non_numeric_capacity_returns_400(self):
        self.assert_validation_error(self.client.get(self.url, {"capacity": "abc"}), "capacity")


class AvailableSlotsTests(ErrorFormatMixin, APISimpleTestCase):
    url = reverse("available-slots")

    def setUp(self):
        self.test_room_id = str(uuid.uuid4())

    def test_valid_query_returns_200(self):
        response = self.client.get(self.url, {"room_id": self.test_room_id, "date": "2026-10-20"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.json()
        self.assertEqual(body["room_id"], self.test_room_id)
        self.assertEqual(body["date"], "2026-10-20")
        self.assertIsInstance(body["available_slots"], list)

    def test_missing_params_returns_400(self):
        self.assert_validation_error(self.client.get(self.url), "room_id", "date")

    def test_invalid_date_returns_400(self):
        self.assert_validation_error(
            self.client.get(self.url, {"room_id": self.test_room_id, "date": "20-10-2026"}), "date"
        )

    def test_invalid_uuid_format_returns_400(self):
        self.assert_validation_error(
            self.client.get(self.url, {"room_id": "not-a-uuid", "date": "2026-10-20"}), "room_id"
        )


class BookingCreateTests(ErrorFormatMixin, APISimpleTestCase):
    url = reverse("booking-list-create")

    def setUp(self):
        teacher = Mock()
        teacher.is_authenticated = True
        teacher.role = "teacher"
        self.client.force_authenticate(user=teacher)

        self.valid_payload = {
            "room_id": str(uuid.uuid4()),
            "lesson_id": str(uuid.uuid4()),
        }

    def test_create_booking_returns_201(self):
        response = self.client.post(self.url, self.valid_payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        body = response.json()
        self.assertEqual(body["status"], "booked")
        self.assertIn("id", body)

    def test_missing_lesson_id_returns_400(self):
        payload = {"room_id": self.valid_payload["room_id"]}
        self.assert_validation_error(self.client.post(self.url, payload, format="json"), "lesson_id")

    def test_invalid_uuid_returns_400(self):
        payload = {**self.valid_payload, "lesson_id": "invalid-uuid"}
        self.assert_validation_error(self.client.post(self.url, payload, format="json"), "lesson_id")


class BookingDeleteTests(APISimpleTestCase):
    def setUp(self):
        dispatcher = Mock()
        dispatcher.is_authenticated = True
        dispatcher.role = "dispatcher"
        self.client.force_authenticate(user=dispatcher)

        self.test_booking_id = str(uuid.uuid4())
        self.unknown_booking_id = "00000000-0000-0000-0000-000000000000"

    def test_delete_existing_booking_returns_204(self):
        response = self.client.delete(reverse("booking-detail", args=[self.test_booking_id]))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_delete_unknown_booking_returns_404(self):
        response = self.client.delete(reverse("booking-detail", args=[self.unknown_booking_id]))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        error = response.json()["error"]
        self.assertEqual(error["code"], "NOT_FOUND")
        self.assertIn("documentation", error)


class UserBookingsTests(ErrorFormatMixin, APISimpleTestCase):
    url = reverse("user-bookings")

    def test_list_user_bookings_returns_200(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.json(), list)

    def test_limit_zero_returns_400(self):
        self.assert_validation_error(self.client.get(self.url, {"limit": 0}), "limit")


class OpenApiSchemaTests(APISimpleTestCase):
    def test_schema_is_served(self):
        response = self.client.get(reverse("schema"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class BookingSecurityTests(APISimpleTestCase):
    """Regression tests for unauthorized booking operations."""

    def setUp(self):
        self.test_booking_id = str(uuid.uuid4())
        self.valid_payload = {
            "room_id": str(uuid.uuid4()),
            "lesson_id": str(uuid.uuid4()),
        }

    def test_anonymous_user_cannot_create_booking(self):
        response = self.client.post(
            reverse("booking-list-create"),
            self.valid_payload,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_anonymous_user_cannot_delete_booking(self):
        response = self.client.delete(reverse("booking-detail", args=[self.test_booking_id]))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_student_cannot_create_booking(self):
        student = Mock()
        student.is_authenticated = True
        student.role = "student"
        self.client.force_authenticate(user=student)

        response = self.client.post(
            reverse("booking-list-create"),
            self.valid_payload,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_student_cannot_delete_booking(self):
        student = Mock()
        student.is_authenticated = True
        student.role = "student"
        self.client.force_authenticate(user=student)

        response = self.client.delete(reverse("booking-detail", args=[self.test_booking_id]))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
