"""
Тести mock-ендпоінтів API (Lab05).

Перевіряють HTTP-коди (200/201/204/400/404) і єдиний формат помилок для пʼяти ендпоінтів.
Ендпоінти поки повертають заглушки й не працюють з базою даних, тому тести наслідують
APISimpleTestCase: тестова база не створюється, і тести однаково проходять на SQLite і PostgreSQL.
Коли зʼявляться моделі, тести на реальні дані треба буде перевести на APITestCase.

Примітка щодо використання ШІ: тести написано з допомогою ШІ (Claude) за кодом
api/views.py та api/serializers.py; перевірено запуском `python manage.py test` локально і в CI.
"""

from unittest.mock import Mock
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APISimpleTestCase, APITestCase

from api.models import Room

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
    # Ендпоінт читає аудиторії з бази (feat/room-crud), тому потрібен APITestCase з тестовою БД.
    url = reverse("room-list")

    def setUp(self):
        Room.objects.create(building="1", number="1-225", capacity=20, projector_working=True)
        Room.objects.create(building="1", number="1-226", capacity=50)

    def test_list_rooms_returns_200(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.json()), 2)
        self.assertEqual(
            set(response.json()[0]), {"id", "building", "number", "capacity", "has_computers", "projector_working"}
        )

    def test_valid_filters_return_200(self):
        response = self.client.get(self.url, {"limit": 5, "offset": 0, "capacity": 30})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([room["number"] for room in response.json()], ["1-226"])

    def test_limit_zero_returns_400(self):
        self.assert_validation_error(self.client.get(self.url, {"limit": 0}), "limit")

    def test_negative_offset_returns_400(self):
        self.assert_validation_error(self.client.get(self.url, {"offset": -1}), "offset")

    def test_non_numeric_capacity_returns_400(self):
        self.assert_validation_error(self.client.get(self.url, {"capacity": "abc"}), "capacity")


class AvailableSlotsTests(ErrorFormatMixin, APISimpleTestCase):
    url = reverse("available-slots")

    def test_valid_query_returns_200(self):
        response = self.client.get(self.url, {"room_id": 1, "date": "2026-10-20"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.json()
        self.assertEqual(body["room_id"], 1)
        self.assertEqual(body["date"], "2026-10-20")
        self.assertIsInstance(body["available_slots"], list)

    def test_missing_params_returns_400(self):
        self.assert_validation_error(self.client.get(self.url), "room_id", "date")

    def test_invalid_date_returns_400(self):
        self.assert_validation_error(self.client.get(self.url, {"room_id": 1, "date": "20-10-2026"}), "date")

    def test_room_id_zero_returns_400(self):
        self.assert_validation_error(self.client.get(self.url, {"room_id": 0, "date": "2026-10-20"}), "room_id")


class BookingCreateTests(ErrorFormatMixin, APISimpleTestCase):
    url = reverse("booking-list-create")
    valid_payload = {
        "room_id": 1,
        "start_time": "2026-10-20T10:00:00Z",
        "end_time": "2026-10-20T11:30:00Z",
        "title": "Програмна інженерія",
    }

    def setUp(self):
        teacher = Mock()
        teacher.is_authenticated = True
        teacher.role = "teacher"
        self.client.force_authenticate(user=teacher)

    def test_create_booking_returns_201(self):
        response = self.client.post(self.url, self.valid_payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        body = response.json()
        self.assertEqual(body["status"], "booked")
        self.assertIn("id", body)
        self.assertEqual(body["title"], self.valid_payload["title"])

    def test_end_before_start_returns_400(self):
        payload = {**self.valid_payload, "end_time": "2026-10-20T09:00:00Z"}
        self.assert_validation_error(self.client.post(self.url, payload, format="json"), "non_field_errors")

    def test_missing_title_returns_400(self):
        payload = {key: value for key, value in self.valid_payload.items() if key != "title"}
        self.assert_validation_error(self.client.post(self.url, payload, format="json"), "title")

    def test_too_long_title_returns_400(self):
        payload = {**self.valid_payload, "title": "x" * 101}
        self.assert_validation_error(self.client.post(self.url, payload, format="json"), "title")


class BookingDeleteTests(APISimpleTestCase):
    def test_delete_existing_booking_returns_204(self):
        response = self.client.delete(reverse("booking-detail", args=[1]))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def setUp(self):
        dispatcher = Mock()
        dispatcher.is_authenticated = True
        dispatcher.role = "dispatcher"
        self.client.force_authenticate(user=dispatcher)

    def test_delete_unknown_booking_returns_404(self):
        response = self.client.delete(reverse("booking-detail", args=[0]))
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

    def test_anonymous_user_cannot_create_booking(self):
        payload = {
            "room_id": 1,
            "start_time": "2026-10-20T10:00:00Z",
            "end_time": "2026-10-20T11:30:00Z",
            "title": "Unauthorized booking",
        }

        response = self.client.post(
            reverse("booking-list-create"),
            payload,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_anonymous_user_cannot_delete_booking(self):
        response = self.client.delete(reverse("booking-detail", args=[1]))

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_student_cannot_create_booking(self):
        student = Mock()
        student.is_authenticated = True
        student.role = "student"
        self.client.force_authenticate(user=student)

        response = self.client.post(
            reverse("booking-list-create"),
            {
                "room_id": 1,
                "start_time": "2026-10-20T10:00:00Z",
                "end_time": "2026-10-20T11:30:00Z",
                "title": "Unauthorized booking",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_student_cannot_delete_booking(self):
        student = Mock()
        student.is_authenticated = True
        student.role = "student"
        self.client.force_authenticate(user=student)

        response = self.client.delete(reverse("booking-detail", args=[1]))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
