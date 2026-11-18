"""
Модели приложения surveys: опросы, вопросы, варианты, сессии ответов и ответы.
"""
from django.db import models
from django.contrib.auth.models import User


class Survey(models.Model):
    """
    Модель опроса (анкеты).
    Создаётся автором, содержит заголовок, описание и статус.
    """
    STATUS_CHOICES = (
        ('draft', 'Черновик'),
        ('published', 'Опубликован'),
        ('closed', 'Завершён'),
    )

    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='surveys',
        verbose_name='Автор опроса'
    )
    title = models.CharField(
        max_length=255,
        verbose_name='Название опроса'
    )
    description = models.TextField(
        blank=True,
        verbose_name='Описание опроса'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft',
        verbose_name='Статус'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )

    class Meta:
        verbose_name = 'Опрос'
        verbose_name_plural = 'Опросы'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} [{self.get_status_display()}]"

    @property
    def response_count(self):
        """Количество собранных ответов респондентов."""
        return self.responses.count()


class Question(models.Model):
    """
    Модель вопроса в опросе.
    Поддерживает 6 игровых и стандартных типов:
    - single: один вариант из списка
    - multiple: несколько вариантов (чекбоксы)
    - text: открытый текстовый ввод
    - rating: звёздный рейтинг (от 1 до 5)
    - emotion: термометр эмоций (от -4 до +4)
    - swipe: свайп карточки влево/вправо (-1 или +1)
    """
    QUESTION_TYPES = (
        ('single', 'Один вариант'),
        ('multiple', 'Несколько вариантов'),
        ('text', 'Текстовый ответ'),
        ('rating', 'Звёздный рейтинг'),
        ('emotion', 'Термометр эмоций'),
        ('swipe', 'Свайп-карточка'),
    )

    survey = models.ForeignKey(
        Survey,
        on_delete=models.CASCADE,
        related_name='questions',
        verbose_name='Опрос'
    )
    text = models.CharField(
        max_length=500,
        verbose_name='Текст вопроса'
    )
    qtype = models.CharField(
        max_length=20,
        choices=QUESTION_TYPES,
        default='single',
        verbose_name='Тип вопроса'
    )
    order = models.PositiveIntegerField(
        default=0,
        verbose_name='Порядковый номер'
    )

    class Meta:
        verbose_name = 'Вопрос'
        verbose_name_plural = 'Вопросы'
        ordering = ['order', 'id']

    def __str__(self):
        return f"{self.order + 1}. {self.text} ({self.get_qtype_display()})"


class Choice(models.Model):
    """
    Вариант ответа для вопросов с выбором (single или multiple).
    """
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name='choices',
        verbose_name='Вопрос'
    )
    text = models.CharField(
        max_length=255,
        verbose_name='Текст варианта'
    )

    class Meta:
        verbose_name = 'Вариант ответа'
        verbose_name_plural = 'Варианты ответов'

    def __str__(self):
        return self.text


class Response(models.Model):
    """
    Сессия прохождения опроса респондентом.
    Ограничение unique_together гарантирует, что каждый человек проходит опрос строго 1 раз.
    """
    survey = models.ForeignKey(
        Survey,
        on_delete=models.CASCADE,
        related_name='responses',
        verbose_name='Опрос'
    )
    respondent = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='survey_responses',
        verbose_name='Респондент'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата прохождения'
    )

    class Meta:
        verbose_name = 'Ответ на опрос'
        verbose_name_plural = 'Ответы на опросы'
        unique_together = ('survey', 'respondent')
        ordering = ['-created_at']

    def __str__(self):
        return f"Ответ от {self.respondent.username} на «{self.survey.title}»"


class Answer(models.Model):
    """
    Конкретный ответ респондента на один вопрос:
    - choice: выбранный вариант (для single/multiple)
    - text: текст (для текстовых вопросов)
    - number: числовое значение (для rating, emotion, swipe)
    """
    response = models.ForeignKey(
        Response,
        on_delete=models.CASCADE,
        related_name='answers',
        verbose_name='Сессия ответа'
    )
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name='answers',
        verbose_name='Вопрос'
    )
    choice = models.ForeignKey(
        Choice,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='answers',
        verbose_name='Выбранный вариант'
    )
    text = models.TextField(
        blank=True,
        default='',
        verbose_name='Текстовый ответ'
    )
    number = models.FloatField(
        null=True,
        blank=True,
        verbose_name='Числовое значение'
    )

    class Meta:
        verbose_name = 'Ответ на вопрос'
        verbose_name_plural = 'Ответы на вопросы'

    def __str__(self):
        return f"Ответ на «{self.question.text[:30]}»"
