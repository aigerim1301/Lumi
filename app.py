"""
Точка входа WSGI для совместимости с Render и хостинг-платформами.
Поддерживает вызовы:
- gunicorn config.wsgi:application
- gunicorn app:app
- gunicorn app:application
"""
import os
import sys
from pathlib import Path

# Добавляем корневой каталог в пути Python
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

# Автоматическая инициализация базы данных, сидера и сбор статики
try:
    from django.db import connection
    from django.core.management import call_command

    # Сбор статических файлов перед запуском WSGI-приложения
    call_command('collectstatic', interactive=False)

    # Применение миграций и создание демо-данных при первом старте
    with connection.cursor() as cursor:
        tables = connection.introspection.table_names(cursor)
        if 'surveys_survey' not in tables:
            print("[Lumi Init] Первый запуск: применение миграций...")
            call_command('migrate', interactive=False)
            print("[Lumi Init] Заполнение демонстрационных данных (seed_demo)...")
            call_command('seed_demo')
            print("[Lumi Init] Инициализация успешно завершена!")
except Exception as e:
    print(f"[Lumi Init Warning]: {e}")

from django.core.wsgi import get_wsgi_application

# Создаём WSGI-приложение Django (WhiteNoise теперь видит все статические файлы)
application = get_wsgi_application()
app = application
