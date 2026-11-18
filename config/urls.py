"""
URL configuration for Lumi project.
"""
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve
from . import views

urlpatterns = [
    # Панель администратора
    path('admin/', admin.site.urls),

    # Авторизация и профили (accounts)
    path('accounts/', include('accounts.urls')),

    # REST API (Django REST Framework)
    path('api/', include('surveys.api_urls')),

    # Опросы, конструктор и статистика (surveys)
    path('', include('surveys.urls')),

    # Вспомогательные маршруты для быстрой демонстрации страниц ошибок на защите
    path('test-403/', views.test_403_view, name='test_403'),
    path('test-404/', views.test_404_view, name='test_404'),

    # Интерактивная презентация курсовой работы
    path('presentation/', views.presentation_view, name='presentation'),

    # Надёжная раздача статических файлов (CSS, картинки) в облаке
    re_path(r'^static/(?P<path>.*)$', serve, {'document_root': settings.STATIC_ROOT}),
]

# Пользовательские обработчики ошибок
handler403 = 'config.views.error_403'
handler404 = 'config.views.error_404'

# Подключение статических файлов в режиме разработки
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
