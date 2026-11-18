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

from django.core.wsgi import get_wsgi_application

# Создаём WSGI-приложение Django
application = get_wsgi_application()
app = application
