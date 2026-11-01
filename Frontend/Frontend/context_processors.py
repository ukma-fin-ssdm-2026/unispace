"""Адреси бекенду для шаблонів: беруться з BACKEND_API_URL, а не вписуються в HTML/JS."""

from django.conf import settings


def backend_urls(request):
    api_url = settings.BACKEND_API_URL.rstrip("/") + "/"
    origin = api_url.split("/api/", 1)[0]
    return {"backend_api_url": api_url, "backend_origin": origin}
