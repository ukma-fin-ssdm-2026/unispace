"""
Вхід і вихід через Microsoft та профіль поточного користувача (NFR-4).

Примітка щодо використання ШІ: модуль згенеровано ШІ (Claude); перевірено тестами test_microsoft_auth.py.
"""

from django.conf import settings
from django.contrib.auth import login, logout
from django.http import HttpResponseRedirect, JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST
from drf_spectacular.utils import extend_schema

from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.services import microsoft_auth
from .models import User

# ==========================================
# Допоміжні функції
# ==========================================


def _error(code, message, http_status):
    return JsonResponse({"error": {"code": code, "message": message}}, status=http_status)

    # ==========================================
    # Вхід та вихід (Authentication)
    # ==========================================


@require_GET
def microsoft_login(request):
    """Перенаправляє браузер на сторінку входу Microsoft."""
    if not microsoft_auth.is_configured():
        return _error("AUTH_NOT_CONFIGURED", "Вхід через Microsoft не налаштовано на сервері", 503)

    flow = microsoft_auth.start_login()
    request.session[microsoft_auth.SESSION_FLOW_KEY] = flow
    return HttpResponseRedirect(flow["auth_uri"])


@require_GET
def microsoft_callback(request):
    """Сюди Microsoft повертає браузер після входу (Redirect URI у реєстрації застосунку)."""
    flow = request.session.pop(microsoft_auth.SESSION_FLOW_KEY, None)
    if flow is None:
        return _error("LOGIN_NOT_STARTED", "Вхід не було розпочато або сесія завершилась", 400)

    try:
        claims = microsoft_auth.finish_login(flow, request.GET.dict())
        user = microsoft_auth.user_from_claims(claims)
    except microsoft_auth.MicrosoftLoginError as error:
        return _error("LOGIN_FAILED", str(error), 400)

    if not user.is_active:
        return _error("USER_INACTIVE", "Обліковий запис вимкнено", 403)

    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    return HttpResponseRedirect(settings.LOGIN_REDIRECT_URL)


@require_GET
@ensure_csrf_cookie
def csrf_token_view(request):
    """
    CSRF-токен для фронтенду на іншому домені: прочитати cookie бекенду він не може, тож отримує токен тут
    і надсилає його в заголовку X-CSRFToken для POST/PATCH/DELETE.
    """
    return JsonResponse({"csrfToken": get_token(request)})


@require_POST
def logout_view(request):
    logout(request)
    return JsonResponse({}, status=200)

    # ==========================================
    # Профіль користувача (API)
    # ==========================================


class CurrentUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "full_name", "role"]


class CurrentUserAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Поточний користувач", responses={200: CurrentUserSerializer})
    def get(self, request, format=None):
        return Response(CurrentUserSerializer(request.user).data, status=status.HTTP_200_OK)
