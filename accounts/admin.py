"""
Настройка панели администратора для приложения accounts.
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import Profile


class ProfileInline(admin.StackedInline):
    """Встраивание профиля прямо в страницу пользователя Django."""
    model = Profile
    can_delete = False
    verbose_name_plural = 'Профиль Lumi'


class UserAdmin(BaseUserAdmin):
    """Расширенный администратор пользователя с профилем."""
    inlines = (ProfileInline,)


# Перерегистрируем стандартную модель User
admin.site.unregister(User)
admin.site.register(User, UserAdmin)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    """Администрирование профилей отдельно."""
    list_display = ('user', 'role', 'dark_theme', 'language', 'notifications')
    list_filter = ('role', 'dark_theme', 'language', 'notifications')
    search_fields = ('user__username', 'user__email', 'user__first_name', 'user__last_name')
