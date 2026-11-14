"""
Тест надійності: перевірка здоров'я сервісу, ін'єкція збою (Бонус, Лаб 9).

Ендпоінт /api/v1/health/ перевіряє доступність бази даних реальним запитом SELECT 1 з тайм-аутом.
Тестовий дублер імітує падіння БД (OperationalError під час виконання запиту), після чого
система має безпечно повернути статус 503 Service Unavailable
із відповідним JSON-повідомленням, а не впасти з помилкою 500.

Запуск: cd Backend && python -m pytest api/tests/reliability/test_health.py -v

Примітка щодо використання ШІ: тест згенеровано з допомогою ШІ
згідно з вимогами до бонусного завдання Лабораторної роботи №9;
інтеграцію, запуск та перевірку працездатності виконано Мельник Дар'єю.
"""

from unittest.mock import patch
from django.db.utils import OperationalError
from django.urls import reverse
from rest_framework import status
import pytest

pytestmark = [pytest.mark.django_db]


@pytest.mark.req("REL-001")
def test_health_check_returns_healthy_when_db_is_up(api_client):
    response = api_client.get(reverse("health-check"))

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "healthy"}


@pytest.mark.req("REL-001")
def test_health_check_returns_unhealthy_on_db_failure(api_client):
    # Act: імітуємо збій бази даних під час спроби отримати курсор / виконати SELECT 1
    with patch("django.db.connection.cursor", side_effect=OperationalError("DB down")):
        response = api_client.get(reverse("health-check"))

    # Assert: маємо отримати статус 503 і зрозуміле повідомлення без витоку деталей
    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.json() == {"status": "unhealthy", "dependency": "database"}
