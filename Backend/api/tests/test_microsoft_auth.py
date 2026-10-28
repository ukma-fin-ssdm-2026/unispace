"""
Тести входу через Microsoft (NFR-4). Справжній Microsoft не викликається: MSAL підмінено моком,
тому тести не потребують секретів і працюють у CI.

Примітка щодо використання ШІ: тести згенеровано ШІ (Claude), переглянуто автором PR.
"""

from unittest.mock import Mock, patch

import pytest
from django.urls import reverse
from rest_framework import status

from api.microsoft_auth import SESSION_FLOW_KEY, MicrosoftLoginError, user_from_claims
from api.models import User

pytestmark = pytest.mark.django_db

TENANT = "11111111-1111-1111-1111-111111111111"
OTHER_TENANT = "22222222-2222-2222-2222-222222222222"
OID = "aaaaaaaa-0000-0000-0000-000000000001"
AUTH_URI = "https://login.microsoftonline.com/fake/authorize"
FAKE_CREDENTIAL = "not-a-real-credential"  # змінна, а не літерал: bandit B105 реагує на присвоєння рядка "секрету"


@pytest.fixture(autouse=True)
def microsoft_settings(settings):
    settings.MS_TENANT_ID = TENANT
    settings.MS_CLIENT_ID = "client-id"
    settings.MS_CLIENT_SECRET = FAKE_CREDENTIAL
    settings.LOGIN_REDIRECT_URL = "/after-login/"
    return settings


def make_claims(**overrides):
    claims = {"tid": TENANT, "oid": OID, "preferred_username": "Student@UKMA.edu.ua", "name": "Олена Студентка"}
    claims.update(overrides)
    return claims


@pytest.fixture
def fake_msal():
    """Підміняє MSAL: initiate_auth_code_flow і acquire_token_by_auth_code_flow повертають задані значення."""
    app = Mock()
    app.initiate_auth_code_flow.return_value = {"auth_uri": AUTH_URI, "state": "xyz"}
    app.acquire_token_by_auth_code_flow.return_value = {"id_token_claims": make_claims()}
    with patch("api.microsoft_auth.build_msal_app", return_value=app):
        yield app


def start_login(client):
    return client.get(reverse("microsoft-login"))


def callback(client):
    return client.get(reverse("microsoft-callback"), {"code": "abc", "state": "xyz"})


# --- Зіставлення користувача з акаунтом Microsoft ---


def test_new_user_is_created_as_student_with_lowercase_email():
    # Act
    user = user_from_claims(make_claims())

    # Assert
    assert user.email == "student@ukma.edu.ua"
    assert user.role == User.RoleChoices.STUDENT
    assert user.external_identity_id == OID
    assert user.full_name == "Олена Студентка"
    assert not user.has_usable_password()


def test_existing_teacher_is_linked_by_email_and_keeps_role(teacher):
    # Arrange: викладач уже є в базі (з розкладу), але ще не входив через Microsoft
    claims = make_claims(preferred_username="TEACHER@ukma.edu.ua")

    # Act
    user = user_from_claims(claims)

    # Assert
    teacher.refresh_from_db()
    assert user == teacher
    assert teacher.role == User.RoleChoices.TEACHER
    assert teacher.external_identity_id == OID


def test_returning_user_is_found_by_microsoft_id_even_if_email_changed(teacher):
    # Arrange
    teacher.external_identity_id = OID
    teacher.save()

    # Act
    user = user_from_claims(make_claims(preferred_username="new.address@ukma.edu.ua"))

    # Assert
    assert user == teacher
    assert User.objects.count() == 1


def test_account_from_another_tenant_is_rejected():
    with pytest.raises(MicrosoftLoginError, match="університету"):
        user_from_claims(make_claims(tid=OTHER_TENANT))


def test_email_bound_to_another_microsoft_account_is_rejected(teacher):
    # Arrange
    teacher.external_identity_id = "another-oid"
    teacher.save()

    # Act / Assert
    with pytest.raises(MicrosoftLoginError, match="іншого акаунта"):
        user_from_claims(make_claims(preferred_username="teacher@ukma.edu.ua"))


@pytest.mark.parametrize("missing", ["oid", "preferred_username"])
def test_claims_without_id_or_email_are_rejected(missing):
    claims = make_claims()
    del claims[missing]

    with pytest.raises(MicrosoftLoginError):
        user_from_claims(claims)


# --- Ендпоінти входу ---


def test_login_redirects_to_microsoft_and_remembers_flow(client, fake_msal):
    # Act
    response = start_login(client)

    # Assert
    assert response.status_code == status.HTTP_302_FOUND
    assert response["Location"] == AUTH_URI
    assert client.session[SESSION_FLOW_KEY]["state"] == "xyz"


def test_login_without_configuration_returns_503(client, settings):
    # Arrange
    settings.MS_CLIENT_SECRET = None

    # Act
    response = start_login(client)

    # Assert
    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


def test_successful_callback_logs_user_in_and_redirects(client, fake_msal):
    # Arrange
    start_login(client)

    # Act
    response = callback(client)

    # Assert
    user = User.objects.get(email="student@ukma.edu.ua")
    assert response.status_code == status.HTTP_302_FOUND
    assert response["Location"] == "/after-login/"
    assert client.session["_auth_user_id"] == str(user.pk)
    assert SESSION_FLOW_KEY not in client.session


def test_callback_without_started_login_returns_400(client, fake_msal):
    # Act
    response = callback(client)

    # Assert
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["error"]["code"] == "LOGIN_NOT_STARTED"


def test_callback_with_microsoft_error_returns_400_and_does_not_log_in(client, fake_msal):
    # Arrange
    start_login(client)
    fake_msal.acquire_token_by_auth_code_flow.return_value = {
        "error": "access_denied",
        "error_description": "Користувач скасував вхід",
    }

    # Act
    response = callback(client)

    # Assert
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "_auth_user_id" not in client.session


def test_callback_with_state_mismatch_returns_400(client, fake_msal):
    # Arrange: MSAL кидає ValueError, якщо state у відповіді не збігається зі збереженим
    start_login(client)
    fake_msal.acquire_token_by_auth_code_flow.side_effect = ValueError("state mismatch")

    # Act
    response = callback(client)

    # Assert
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_inactive_user_cannot_log_in(client, fake_msal, teacher):
    # Arrange
    teacher.is_active = False
    teacher.save()
    fake_msal.acquire_token_by_auth_code_flow.return_value = {
        "id_token_claims": make_claims(preferred_username="teacher@ukma.edu.ua")
    }
    start_login(client)

    # Act
    response = callback(client)

    # Assert
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "_auth_user_id" not in client.session


def test_current_user_endpoint_returns_profile_after_login(client, fake_msal):
    # Arrange
    start_login(client)
    callback(client)

    # Act
    response = client.get(reverse("current-user"))

    # Assert
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["email"] == "student@ukma.edu.ua"
    assert response.json()["role"] == "student"


def test_current_user_endpoint_requires_login(client):
    # Act
    response = client.get(reverse("current-user"))

    # Assert
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_logout_ends_session(client, teacher):
    # Arrange
    client.force_login(teacher)

    # Act
    response = client.post(reverse("logout"))

    # Assert
    assert response.status_code == status.HTTP_200_OK
    assert "_auth_user_id" not in client.session
