"""
Модели приложения accounts: профиль пользователя и его настройки.
"""
from django.db import models
from django.contrib.auth.models import User


class Profile(models.Model):
    """
    Профиль пользователя Lumi.
    Расширяет стандартного пользователя Django связью OneToOne:
    - роль (автор опросов или респондент)
    - переключатель тёмной темы
    - язык интерфейса (русский, английский, кыргызский)
    - настройки уведомлений
    """
    ROLE_CHOICES = (
        ('author', 'Автор опросов'),
        ('respondent', 'Респондент'),
    )
    LANGUAGE_CHOICES = (
        ('ru', 'Русский'),
    )

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile',
        verbose_name='Пользователь'
    )
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='respondent',
        verbose_name='Роль'
    )
    dark_theme = models.BooleanField(
        default=False,
        verbose_name='Тёмная тема'
    )
    language = models.CharField(
        max_length=10,
        choices=LANGUAGE_CHOICES,
        default='ru',
        verbose_name='Язык'
    )
    notifications = models.BooleanField(
        default=True,
        verbose_name='Уведомления'
    )

    class Meta:
        verbose_name = 'Профиль пользователя'
        verbose_name_plural = 'Профили пользователей'

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"
