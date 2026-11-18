"""
Классы разрешений (permissions) для Django REST Framework.
"""
from rest_framework import permissions


class IsSurveyAuthor(permissions.BasePermission):
    """
    Разрешение: доступ разрешён только автору конкретного опроса или администратору.
    Остальным пользователям (включая респондентов) возвращается HTTP 403 Forbidden.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if request.user.is_staff or request.user.is_superuser:
            return True
        return hasattr(obj, 'author') and obj.author == request.user
