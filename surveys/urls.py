"""
Маршруты приложения surveys.
"""
from django.urls import path
from . import views

urlpatterns = [
    # Список опросов (главная страница)
    path('', views.survey_list, name='survey_list'),

    # Создание опроса и конструктор
    path('create/', views.survey_create, name='survey_create'),
    path('create/ai/', views.survey_create_with_ai, name='survey_create_with_ai'),
    path('<int:pk>/builder/', views.survey_builder, name='survey_builder'),
    path('<int:pk>/ai-generate/', views.survey_ai_generate, name='survey_ai_generate'),

    # Публикация, удаление и управление вопросами
    path('<int:pk>/publish/', views.survey_publish, name='survey_publish'),
    path('<int:pk>/delete/', views.survey_delete, name='survey_delete'),
    path('<int:pk>/questions/add/', views.survey_add_question, name='survey_add_question'),
    path('<int:pk>/questions/<int:q_pk>/delete/', views.survey_delete_question, name='survey_delete_question'),

    # Прохождение опроса и карточка-итог (этап 5)
    path('<int:pk>/respond/', views.survey_respond, name='survey_respond'),
    path('<int:pk>/result/', views.survey_result, name='survey_result'),

    # Раздел статистики и экспорт CSV (этап 6)
    path('<int:pk>/stats/', views.survey_stats, name='survey_stats'),
    path('<int:pk>/export/csv/', views.survey_export_csv, name='survey_export_csv'),
    path('stats/', views.stats_summary, name='stats_summary'),
]
