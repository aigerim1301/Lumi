"""
API-представления Django REST Framework для Lumi.
"""
from rest_framework.views import APIView
from rest_framework.response import Response as RestResponse
from rest_framework import status, permissions
from django.shortcuts import get_object_or_404
from .models import Survey
from .serializers import (
    UserProfileSerializer,
    SurveyListSerializer,
    SurveyDetailSerializer,
    SurveyResponseSubmitSerializer
)
from .api_permissions import IsSurveyAuthor
from .stats import calculate_survey_statistics


class CurrentUserAPIView(APIView):
    """
    GET /api/me/
    Возвращает информацию о текущем авторизованном пользователе, его роли и настройках.
    Доступ: только для авторизованных пользователей (401/403 без авторизации).
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        serializer = UserProfileSerializer(request.user)
        return RestResponse(serializer.data)


class SurveyListAPIView(APIView):
    """
    GET /api/surveys/
    Возвращает список доступных опубликованных опросов (или своих опросов при ?mine=true для автора).
    Доступ: только для авторизованных пользователей.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        mine = request.query_params.get('mine', '').lower() in ('true', '1')

        if mine:
            # Свои опросы автора
            surveys = Survey.objects.filter(author=user)
        else:
            # Опубликованные опросы для прохождения
            surveys = Survey.objects.filter(status='published')

        serializer = SurveyListSerializer(surveys, many=True)
        return RestResponse(serializer.data)


class SurveyDetailAPIView(APIView):
    """
    GET /api/surveys/<id>/
    Возвращает подробную структуру опроса, включая все вопросы и варианты ответов.
    Доступ: только для авторизованных пользователей.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        survey = get_object_or_404(Survey, pk=pk)

        # Респонденты могут видеть только опубликованные опросы
        is_author_or_admin = (survey.author == request.user) or request.user.is_staff
        if survey.status != 'published' and not is_author_or_admin:
            return RestResponse(
                {'detail': 'Опрос не опубликован и недоступен.'},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = SurveyDetailSerializer(survey)
        return RestResponse(serializer.data)


class SurveyRespondAPIView(APIView):
    """
    POST /api/surveys/<id>/respond/
    Принимает и валидирует ответы респондента на опрос.
    Ограничение: один пользователь может пройти опрос строго 1 раз.
    Доступ: только для авторизованных пользователей.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        survey = get_object_or_404(Survey, pk=pk)

        serializer = SurveyResponseSubmitSerializer(
            data=request.data,
            context={'request': request, 'survey': survey}
        )

        if serializer.is_valid():
            response_obj = serializer.save()
            return RestResponse(
                {
                    'status': 'ok',
                    'message': 'Ответы успешно сохранены!',
                    'response_id': response_obj.id,
                    'survey_id': survey.id
                },
                status=status.HTTP_201_CREATED
            )

        return RestResponse(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SurveyStatsAPIView(APIView):
    """
    GET /api/surveys/<id>/stats/
    Возвращает подробную статистику опроса:
    - общее число ответов и завершённость
    - динамику ответов по дням
    - данные для круговой диаграммы
    - подробную аналитику по каждому вопросу (средний балл, эмоции, свайпы)
    Доступ: ТОЛЬКО автор этого опроса или администратор (остальным 403 Forbidden).
    """
    permission_classes = [permissions.IsAuthenticated, IsSurveyAuthor]

    def get(self, request, pk):
        survey = get_object_or_404(Survey, pk=pk)

        # Проверка прав доступа через permission_class
        self.check_object_permissions(request, survey)

        stats_data = calculate_survey_statistics(survey)

        # Сериализуем данные для отдачи в чистом JSON
        return RestResponse({
            'survey_id': survey.id,
            'survey_title': survey.title,
            'author': survey.author.username,
            'total_responses': stats_data['total_responses'],
            'completion_rate': stats_data['completion_rate'],
            'days_labels': stats_data['days_labels'],
            'days_counts': stats_data['days_counts'],
            'primary_chart': stats_data['primary_chart'],
            'questions_analysis': stats_data['questions_analysis'],
        })
