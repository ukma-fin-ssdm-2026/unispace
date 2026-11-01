from django.shortcuts import render
from django.views.decorators.http import require_GET


@require_GET
def login_view(request):
    request.session.pop("has_seen_welcome", None)
    return render(request, "login.html")


@require_GET
def home_view(request):
    # Перевіряємо сесію для показу привітання
    show_welcome = not request.session.get("has_seen_welcome", False)

    if show_welcome:
        request.session["has_seen_welcome"] = True

    context = {
        "show_welcome": show_welcome,
    }
    return render(request, "home.html", context)


@require_GET
def bookings_view(request):
    """Мої бронювання: зміна аудиторії та скасування (викладач, диспетчер). Дані завантажує bookings.js."""
    return render(request, "bookings.html")


@require_GET
def saz_import_view(request):
    """Імпорт розкладу із САЗ (диспетчер). Дані надсилає й показує saz_import.js."""
    return render(request, "saz_import.html")
