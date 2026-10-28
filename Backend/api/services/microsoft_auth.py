"""
Вхід через університетський акаунт Microsoft (Entra ID, OpenID Connect) - NFR-4.

Потік Authorization Code: бекенд перенаправляє на сторінку входу Microsoft, а після повернення
обмінює код на id_token через бібліотеку MSAL (вона ж перевіряє state і nonce).
З id_token беремо лише незмінний ID користувача (oid), тенант (tid), пошту та ім'я.

Роль Microsoft не повідомляє, тому її визначає наша база: викладачі приходять з розкладу САЗ,
диспетчера призначає адміністратор, а новий користувач за замовчуванням - студент.

Примітка щодо використання ШІ: модуль згенеровано ШІ (Claude); логіку
зіставлення користувачів узгоджено з командою, поведінку перевіряють
тести test_microsoft_auth.py з підміною MSAL.
"""

import msal
from django.conf import settings

from api.models import User

LOGIN_SCOPES = ["User.Read"]
SESSION_FLOW_KEY = "microsoft_auth_flow"


class MicrosoftLoginError(Exception):
    """Вхід не вдався: відповідь Microsoft невалідна або користувача не можна пустити."""

    # ==========================================
    # Налаштування та конфігурація MSAL
    # ==========================================


def is_configured():
    return bool(settings.MS_TENANT_ID and settings.MS_CLIENT_ID and settings.MS_CLIENT_SECRET)


def build_msal_app():
    return msal.ConfidentialClientApplication(
        settings.MS_CLIENT_ID,
        authority=f"https://login.microsoftonline.com/{settings.MS_TENANT_ID}",
        client_credential=settings.MS_CLIENT_SECRET,
    )

    # ==========================================
    # Потік авторизації (Auth Code Flow)
    # ==========================================


def start_login():
    """Повертає flow (зберігається в сесії) з адресою auth_uri, куди треба перенаправити браузер."""
    return build_msal_app().initiate_auth_code_flow(LOGIN_SCOPES, redirect_uri=settings.MS_REDIRECT_URI)


def finish_login(flow, query_params):
    """Обмінює код із запиту повернення на claims з id_token."""
    try:
        result = build_msal_app().acquire_token_by_auth_code_flow(flow, query_params)
    except ValueError as error:  # MSAL кидає ValueError, якщо state не збігається
        raise MicrosoftLoginError("Невалідна відповідь Microsoft") from error

    if "error" in result:
        raise MicrosoftLoginError(result.get("error_description") or result["error"])

    claims = result.get("id_token_claims")
    if not claims:
        raise MicrosoftLoginError("Microsoft не повернув id_token")
    return claims

    # ==========================================
    # Зіставлення користувачів (БД)
    # ==========================================


def user_from_claims(claims):
    """Знаходить або створює користувача за claims з id_token. Роль існуючого користувача не змінюється."""
    if claims.get("tid") != settings.MS_TENANT_ID:
        raise MicrosoftLoginError("Акаунт не належить до університету")

    object_id = claims.get("oid")
    email = (claims.get("email") or claims.get("preferred_username") or "").strip().lower()
    if not object_id or not email:
        raise MicrosoftLoginError("У відповіді Microsoft немає ID користувача або пошти")

    user = User.objects.filter(external_identity_id=object_id).first()
    if user is not None:
        return user

    user = User.objects.filter(email__iexact=email).first()
    if user is not None:
        # Користувач уже є (наприклад, викладач з розкладу САЗ) - прив'язуємо його до акаунта Microsoft.
        if user.external_identity_id:
            raise MicrosoftLoginError("Ця пошта вже прив'язана до іншого акаунта Microsoft")
        user.external_identity_id = object_id
        if not user.full_name:
            user.full_name = claims.get("name", "")
        user.save(update_fields=["external_identity_id", "full_name"])
        return user

    user = User(email=email, external_identity_id=object_id, full_name=claims.get("name", ""))
    user.set_unusable_password()
    user.save()
    return user
