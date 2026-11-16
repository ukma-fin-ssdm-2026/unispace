"""
Тести надійності для Microsoft OAuth (REL-H08, Лаб 9).

Перевіряють:
1. Явне передавання timeout у msal.ConfidentialClientApplication.
2. Перетворення мережевих збоїв (RequestException / Timeout / ConnectionError)
   у start_login() та finish_login() на контрольований MicrosoftLoginError
   із записом у серверний лог та поверненням контрольованої HTTP-відповіді (без 500).
3. Приховування сирого error_description від Microsoft (Trace ID / AADSTS-коди)
   від кінцевого користувача з логуванням деталей на сервері.

Запуск: cd Backend && python -m pytest api/tests/reliability/test_microsoft_auth_reliability.py -v

Примітка щодо використання ШІ: тести згенеровано за допомогою ШІ (Gemini)
для закриття знахідки REL-H08; перевірено та інтегровано Мельник Дар'єю.
"""

from unittest.mock import MagicMock, patch
import pytest
import requests
from django.test import override_settings
from django.urls import reverse
from rest_framework import status

from api.services import microsoft_auth
from api.services.microsoft_auth import MicrosoftLoginError, SESSION_FLOW_KEY

pytestmark = [pytest.mark.django_db, pytest.mark.req("REL-002")]

FAKE_CREDENTIAL = "not-a-real-credential"

# ==========================================
# Конфігурація та тайм-аути клієнта MSAL
# ==========================================


@override_settings(
    MS_TENANT_ID="tenant-123",
    MS_CLIENT_ID="client-123",
    MS_CLIENT_SECRET=FAKE_CREDENTIAL,
    MS_REDIRECT_URI="http://testserver/auth/microsoft/callback/",
)
def test_build_msal_app_sets_explicit_http_timeout():
    with patch("api.services.microsoft_auth.msal.ConfidentialClientApplication") as mock_msal_cls:
        microsoft_auth.build_msal_app()

    mock_msal_cls.assert_called_once_with(
        "client-123",
        authority="https://login.microsoftonline.com/tenant-123",
        client_credential=FAKE_CREDENTIAL,
        timeout=microsoft_auth.MSAL_HTTP_TIMEOUT_SECONDS,
    )

    # ==========================================
    # Ін'єкція мережевих збоїв (OAuth HTTP Flows)
    # ==========================================


@pytest.mark.parametrize(
    "network_error",
    [
        requests.exceptions.Timeout("MSAL discovery timed out"),
        requests.exceptions.ConnectionError("DNS failure"),
        ValueError("Failed to get authority configuration"),
    ],
)
@override_settings(
    MS_TENANT_ID="tenant-123",
    MS_CLIENT_ID="client-123",
    MS_CLIENT_SECRET=FAKE_CREDENTIAL,
    MS_REDIRECT_URI="http://testserver/auth/microsoft/callback/",
)
def test_start_login_network_failure_returns_controlled_503_and_logs(client, network_error, caplog):
    with patch("api.services.microsoft_auth.build_msal_app", side_effect=network_error):
        response = client.get(reverse("microsoft-login"))

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    payload = response.json()
    assert payload["error"]["code"] == "LOGIN_FAILED"
    assert payload["error"]["message"] == microsoft_auth.MS_UNAVAILABLE_MESSAGE
    assert SESSION_FLOW_KEY not in client.session
    assert any("Помилка звернення до Microsoft під час ініціалізації входу" in rec.message for rec in caplog.records)


@pytest.mark.parametrize(
    "network_error",
    [
        requests.exceptions.Timeout("Token exchange timed out"),
        requests.exceptions.ConnectionError("Connection reset by peer"),
    ],
)
def test_finish_login_network_failure_returns_controlled_400_and_logs(client, network_error, caplog):
    session = client.session
    session[SESSION_FLOW_KEY] = {"state": "xyz"}
    session.save()

    mock_app = MagicMock()
    mock_app.acquire_token_by_auth_code_flow.side_effect = network_error

    with patch("api.services.microsoft_auth.build_msal_app", return_value=mock_app):
        response = client.get(reverse("microsoft-callback"), {"code": "abc", "state": "xyz"})

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    payload = response.json()
    assert payload["error"]["code"] == "LOGIN_FAILED"
    assert payload["error"]["message"] == microsoft_auth.MS_UNAVAILABLE_MESSAGE
    assert "_auth_user_id" not in client.session
    assert any("Помилка мережі під час звернення до Microsoft" in rec.message for rec in caplog.records)

    # ==========================================
    # Безпека повідомлень про помилки (Error Sanitization)
    # ==========================================


def test_finish_login_hides_raw_microsoft_error_description_from_user(caplog):
    raw_ms_error = {
        "error": "invalid_grant",
        "error_description": "AADSTS70000: Provided grant is invalid. Trace ID: 9f8a7b-secret-guid",
    }
    mock_app = MagicMock()
    mock_app.acquire_token_by_auth_code_flow.return_value = raw_ms_error

    with patch("api.services.microsoft_auth.build_msal_app", return_value=mock_app):
        with pytest.raises(MicrosoftLoginError) as exc_info:
            microsoft_auth.finish_login({"state": "s1"}, {"code": "c1", "state": "s1"})

    assert str(exc_info.value) == microsoft_auth.MS_AUTH_REJECTED_MESSAGE
    assert "AADSTS70000" not in str(exc_info.value)
    assert "9f8a7b-secret-guid" not in str(exc_info.value)
    assert any("AADSTS70000" in rec.message for rec in caplog.records)
