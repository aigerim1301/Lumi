"""
Модуль проверки прав доступа (permissions) для приложения surveys.
"""
from functools import wraps
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.contrib import messages


def author_required(view_func):
    """
    Декоратор: разрешает доступ только авторам опросов или администраторам.
    Если пользователь не вошел в систему — перенаправляет на страницу входа.
    Если вошел, но его роль 'respondent' — выбрасывает PermissionDenied (ошибка 403).
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.warning(request, 'Пожалуйста, войдите в систему для доступа к этому разделу.')
            return redirect('login')

        profile = getattr(request.user, 'profile', None)
        is_author = profile and profile.role == 'author'
        is_admin = request.user.is_staff or request.user.is_superuser

        if not (is_author or is_admin):
            # Респондент не имеет доступа к конструктору и чужому управлению
            raise PermissionDenied("Конструктор и управление опросами доступны только авторам.")

        return view_func(request, *args, **kwargs)

    return _wrapped_view
