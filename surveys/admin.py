"""
Настройка панели администратора для моделей опросов (surveys).
"""
from django.contrib import admin
from .models import Survey, Question, Choice, Response, Answer


class ChoiceInline(admin.TabularInline):
    """Встраивание вариантов ответа прямо в форму вопроса."""
    model = Choice
    extra = 2


class QuestionInline(admin.StackedInline):
    """Встраивание вопросов в форму опроса."""
    model = Question
    extra = 1
    show_change_link = True


class AnswerInline(admin.TabularInline):
    """Встраивание ответов в просмотр сессии респондента."""
    model = Answer
    extra = 0
    readonly_fields = ('question', 'choice', 'text', 'number')
    can_delete = False


@admin.register(Survey)
class SurveyAdmin(admin.ModelAdmin):
    """Администрирование опросов."""
    list_display = ('title', 'author', 'status', 'response_count', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('title', 'description', 'author__username')
    inlines = [QuestionInline]


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    """Администрирование отдельных вопросов."""
    list_display = ('text', 'survey', 'qtype', 'order')
    list_filter = ('qtype', 'survey')
    search_fields = ('text', 'survey__title')
    inlines = [ChoiceInline]


@admin.register(Choice)
class ChoiceAdmin(admin.ModelAdmin):
    """Администрирование вариантов ответа."""
    list_display = ('text', 'question')
    search_fields = ('text', 'question__text')


@admin.register(Response)
class ResponseAdmin(admin.ModelAdmin):
    """Администрирование сессий прохождений."""
    list_display = ('survey', 'respondent', 'created_at')
    list_filter = ('survey', 'created_at')
    search_fields = ('survey__title', 'respondent__username')
    inlines = [AnswerInline]


@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    """Администрирование конкретных ответов."""
    list_display = ('question', 'response', 'choice', 'number', 'text')
    list_filter = ('question__qtype',)
    search_fields = ('question__text', 'text', 'response__respondent__username')
