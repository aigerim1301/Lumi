"""
Маршруты REST API (Django REST Framework) для платформы Lumi.
"""
from django.urls import path
from . import api_views

urlpatterns = [
    # Текущий профиль пользователя
    path('me/', api_views.CurrentUserAPIView.as_view(), name='api_me'),

    # Список и детали опросов
    path('surveys/', api_views.SurveyListAPIView.as_view(), name='api_survey_list'),
    path('surveys/<int:pk>/', api_views.SurveyDetailAPIView.as_view(), name='api_survey_detail'),

    # Отправка ответов респондентом
    path('surveys/<int:pk>/respond/', api_views.SurveyRespondAPIView.as_view(), name='api_survey_respond'),

    # Аналитика и статистика (только для автора)
    path('surveys/<int:pk>/stats/', api_views.SurveyStatsAPIView.as_view(), name='api_survey_stats'),
]
