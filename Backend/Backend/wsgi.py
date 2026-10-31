"""
WSGI config for Backend project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.1/howto/deployment/wsgi/
"""

import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Backend.settings")

# Автоматичний запуск міграцій при запуску на Render (немає доступу до платних Shell)
if not os.environ.get("DEBUG", "False") == "True":
    try:
        from django.core.management import call_command

        call_command("migrate", interactive=False)
    except Exception as e:
        print(f"Migration error: {e}")

application = get_wsgi_application()
