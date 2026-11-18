"""
Сериализаторы Django REST Framework для платформы Lumi.
"""
from rest_framework import serializers
from django.contrib.auth.models import User
from accounts.models import Profile
from .models import Survey, Question, Choice, Response, Answer


class UserProfileSerializer(serializers.ModelSerializer):
    """Сериализатор текущего пользователя и его настроек (эндпоинт /api/me/)."""
    role = serializers.CharField(source='profile.role', read_only=True)
    role_display = serializers.CharField(source='profile.get_role_display', read_only=True)
    dark_theme = serializers.BooleanField(source='profile.dark_theme')
    language = serializers.CharField(source='profile.language')
    notifications = serializers.BooleanField(source='profile.notifications')
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'full_name', 'role', 'role_display', 'dark_theme', 'language', 'notifications'
        ]
        read_only_fields = ['id', 'username', 'role', 'role_display']

    def get_full_name(self, obj):
        return obj.get_full_name() or obj.username


class ChoiceSerializer(serializers.ModelSerializer):
    """Сериализатор вариантов ответа к вопросу."""
    class Meta:
        model = Choice
        fields = ['id', 'text']


class QuestionSerializer(serializers.ModelSerializer):
    """Сериализатор вопроса с вложенными вариантами ответа."""
    choices = ChoiceSerializer(many=True, read_only=True)
    qtype_display = serializers.CharField(source='get_qtype_display', read_only=True)

    class Meta:
        model = Question
        fields = ['id', 'text', 'qtype', 'qtype_display', 'order', 'choices']


class SurveyListSerializer(serializers.ModelSerializer):
    """Сериализатор списка опросов (для каталога и списка автора)."""
    author_username = serializers.CharField(source='author.username', read_only=True)
    author_name = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    questions_count = serializers.IntegerField(source='questions.count', read_only=True)
    responses_count = serializers.IntegerField(source='response_count', read_only=True)

    class Meta:
        model = Survey
        fields = [
            'id', 'title', 'description', 'status', 'status_display',
            'author_username', 'author_name', 'questions_count',
            'responses_count', 'created_at'
        ]

    def get_author_name(self, obj):
        return obj.author.get_full_name() or obj.author.username


class SurveyDetailSerializer(serializers.ModelSerializer):
    """Подробный сериализатор опроса со всеми вопросами и вариантами."""
    author_username = serializers.CharField(source='author.username', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    questions = QuestionSerializer(many=True, read_only=True)
    responses_count = serializers.IntegerField(source='response_count', read_only=True)

    class Meta:
        model = Survey
        fields = [
            'id', 'title', 'description', 'status', 'status_display',
            'author_username', 'questions', 'responses_count', 'created_at'
        ]


class SingleAnswerSubmitSerializer(serializers.Serializer):
    """Сериализатор одного ответа респондента."""
    question_id = serializers.IntegerField()
    choice_id = serializers.IntegerField(required=False, allow_null=True)
    text = serializers.CharField(required=False, allow_blank=True, default='')
    number = serializers.FloatField(required=False, allow_null=True)


class SurveyResponseSubmitSerializer(serializers.Serializer):
    """
    Сериализатор отправки ответов на опрос через API:
    - Проверяет, что опрос опубликован
    - Проверяет, что пользователь еще не проходил этот опрос
    - Сохраняет ответы с валидацией типов
    """
    answers = SingleAnswerSubmitSerializer(many=True)

    def validate(self, attrs):
        survey = self.context['survey']
        user = self.context['request'].user

        # Проверка публикации опроса
        if survey.status != 'published':
            raise serializers.ValidationError('Опрос не опубликован и недоступен для прохождения.')

        # Проверка повторного прохождения
        if Response.objects.filter(survey=survey, respondent=user).exists():
            raise serializers.ValidationError('Вы уже прошли этот опрос. Повторное прохождение запрещено.')

        if not attrs.get('answers'):
            raise serializers.ValidationError('Список ответов не может быть пустым.')

        return attrs

    def save(self):
        survey = self.context['survey']
        user = self.context['request'].user
        answers_data = self.validated_data['answers']

        response_obj = Response.objects.create(
            survey=survey,
            respondent=user
        )

        created_answers = []
        for item in answers_data:
            q_id = item['question_id']
            question = Question.objects.filter(id=q_id, survey=survey).first()
            if not question:
                continue

            choice_obj = None
            if item.get('choice_id'):
                choice_obj = Choice.objects.filter(id=item['choice_id'], question=question).first()

            ans = Answer.objects.create(
                response=response_obj,
                question=question,
                choice=choice_obj,
                text=item.get('text', ''),
                number=item.get('number')
            )
            created_answers.append(ans)

        return response_obj
