"""
Сигналы Django для автоматического создания профиля пользователя.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Profile


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """
    Автоматически создаёт объект Profile при регистрации нового пользователя Django.
    """
    if created:
        Profile.objects.get_or_create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """
    Сохраняет профиль при обновлении пользователя, если профиль существует.
    """
    if hasattr(instance, 'profile'):
        instance.profile.save()
