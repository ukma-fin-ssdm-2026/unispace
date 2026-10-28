from django.shortcuts import render


def home_view(request):
    context = {
        "page_title": "Dashboard - UniSpace",
        "welcome_message": "Ласкаво просимо до UniSpace!",
        # Спробуйте змінити 'dispatcher' на 'student' або 'teacher',
        # щоб побачити, як меню автоматично приховує зайві пункти
        "user_role": "dispatcher",
    }
    return render(request, "home.html", context)
