"""
Контекстные процессоры для передачи глобальных переменных в шаблоны Lumi.
"""
from django.conf import settings


def lumi_settings(request):
    """
    Добавляет переменные настроек во все шаблоны:
    - BRAND_NAME: название платформы (Lumi)
    """
    return {
        'BRAND_NAME': getattr(settings, 'BRAND_NAME', 'Lumi'),
    }
