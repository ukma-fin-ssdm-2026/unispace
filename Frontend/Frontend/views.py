from django.shortcuts import render
from django.views.decorators.http import require_GET


@require_GET
def login_view(request):
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
