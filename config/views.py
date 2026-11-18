"""
Базовые представления и обработчики ошибок проекта Lumi.
"""
from django.shortcuts import render
from django.core.exceptions import PermissionDenied
from django.http import Http404


def error_403(request, exception=None):
    """
    Пользовательская страница ошибки 403 (Доступ запрещен).
    Возвращает статус HTTP 403 Forbidden.
    """
    return render(request, '403.html', status=403)


def error_404(request, exception=None):
    """
    Пользовательская страница ошибки 404 (Страница не найдена).
    Возвращает статус HTTP 404 Not Found.
    """
    return render(request, '404.html', status=404)


def test_403_view(request):
    """Вспомогательный маршрут для быстрой проверки страницы 403 на защите."""
    raise PermissionDenied("Тестовый вызов страницы 403")


def test_404_view(request):
    """Вспомогательный маршрут для быстрой проверки страницы 404 на защите."""
    raise Http404("Тестовый вызов страницы 404")

