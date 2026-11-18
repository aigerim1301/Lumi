from django.test import TestCase, Client
from django.conf import settings
from django.contrib.auth.models import User
from django.core.management import call_command
from django.db import IntegrityError
from accounts.models import Profile
from surveys.models import Survey, Question, Choice, Response, Answer


class FoundationTests(TestCase):
    """
    Тесты базового фундамента проекта (Этап 1):
    - Доступность главной страницы
    - Наличие названия бренда Lumi в шаблоне
    - Корректность кодов и страниц ошибок 403 и 404
    """

    def setUp(self):
        self.client = Client()

    def test_home_page_status_and_brand(self):
        """Проверка главной страницы и названия бренда."""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, settings.BRAND_NAME)
        self.assertTemplateUsed(response, 'base.html')
        self.assertTemplateUsed(response, 'home.html')

    def test_custom_403_page(self):
        """Проверка кода 403 и пользовательского шаблона."""
        response = self.client.get('/test-403/')
        self.assertEqual(response.status_code, 403)
        self.assertTemplateUsed(response, '403.html')
        self.assertContains(response, 'Доступ ограничен', status_code=403)

    def test_custom_404_page(self):
        """Проверка кода 404 и пользовательского шаблона."""
        response = self.client.get('/definitely-non-existent-page-12345/')
        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, '404.html')
        self.assertContains(response, 'Страница не найдена', status_code=404)


class ModelAndSignalTests(TestCase):
    """
    Тесты моделей, сигналов и ограничений базы данных (Этап 2):
    - Автосоздание профиля через сигнал post_save
    - Связи Survey, Question, Choice
    - Уникальность ответа (один респондент на опрос один раз)
    - Проверка работы команды seed_demo
    """

    def setUp(self):
        self.author_user = User.objects.create_user(username='test_author', password='password123')
        self.author_user.profile.role = 'author'
        self.author_user.profile.save()

        self.respondent_user = User.objects.create_user(username='test_resp', password='password123')

    def test_profile_auto_creation_signal(self):
        """Проверяем, что сигнал post_save автоматически создал профиль."""
        new_user = User.objects.create_user(username='auto_profile_user', password='password123')
        self.assertTrue(hasattr(new_user, 'profile'))
        self.assertEqual(new_user.profile.role, 'respondent')
        self.assertEqual(new_user.profile.language, 'ru')
        self.assertFalse(new_user.profile.dark_theme)

    def test_survey_and_questions_creation(self):
        """Проверяем создание опроса, вопросов и вариантов ответов."""
        survey = Survey.objects.create(
            author=self.author_user,
            title='Тестовый опрос',
            description='Описание теста',
            status='published'
        )
        self.assertEqual(str(survey), 'Тестовый опрос [Опубликован]')

        q_single = Question.objects.create(
            survey=survey,
            text='Вопрос с одним выбором',
            qtype='single',
            order=0
        )
        Choice.objects.create(question=q_single, text='Вариант 1')
        Choice.objects.create(question=q_single, text='Вариант 2')

        self.assertEqual(q_single.choices.count(), 2)
        self.assertEqual(survey.questions.count(), 1)
        self.assertEqual(survey.response_count, 0)

    def test_unique_response_constraint(self):
        """Проверяем, что один пользователь не может пройти один опрос дважды."""
        survey = Survey.objects.create(author=self.author_user, title='Опрос для проверки дублей')
        
        # Первый ответ сохраняется успешно
        Response.objects.create(survey=survey, respondent=self.respondent_user)
        self.assertEqual(survey.response_count, 1)

        # Повторная попытка должна вызвать ошибку IntegrityError
        with self.assertRaises(IntegrityError):
            Response.objects.create(survey=survey, respondent=self.respondent_user)

    def test_answer_types_saving(self):
        """Проверяем сохранение числовых (rating/emotion/swipe) и текстовых ответов."""
        survey = Survey.objects.create(author=self.author_user, title='Опрос типов ответов')
        q_rating = Question.objects.create(survey=survey, text='Оценка', qtype='rating')
        q_text = Question.objects.create(survey=survey, text='Отзыв', qtype='text')

        resp = Response.objects.create(survey=survey, respondent=self.respondent_user)
        ans_num = Answer.objects.create(response=resp, question=q_rating, number=4.5)
        ans_txt = Answer.objects.create(response=resp, question=q_text, text='Отличный курс!')

        self.assertEqual(ans_num.number, 4.5)
        self.assertEqual(ans_txt.text, 'Отличный курс!')
        self.assertEqual(resp.answers.count(), 2)

    def test_seed_demo_command(self):
        """Проверяем, что management-команда seed_demo отрабатывает без ошибок."""
        call_command('seed_demo')
        self.assertTrue(User.objects.filter(username='admin').exists())
        self.assertTrue(User.objects.filter(username='author').exists())
        self.assertTrue(User.objects.filter(username='respondent').exists())
        self.assertTrue(Survey.objects.filter(author__username='author').count() >= 2)
        self.assertTrue(Response.objects.count() >= 5)


class SurveyBuilderAndPermissionTests(TestCase):
    """
    Тесты конструктора опросов и прав доступа (Этап 4):
    - Респондент не может открыть конструктор (403)
    - Автор не может редактировать чужой опрос (403)
    - Автор может создавать, публиковать и удалять свои опросы
    """

    def setUp(self):
        self.client = Client()

        self.author1 = User.objects.create_user(username='author1', password='Password123!')
        self.author1.profile.role = 'author'
        self.author1.profile.save()

        self.author2 = User.objects.create_user(username='author2', password='Password123!')
        self.author2.profile.role = 'author'
        self.author2.profile.save()

        self.respondent = User.objects.create_user(username='resp_user', password='Password123!')
        self.respondent.profile.role = 'respondent'
        self.respondent.profile.save()

        self.survey1 = Survey.objects.create(
            author=self.author1,
            title='Опрос первого автора',
            status='draft'
        )

    def test_respondent_cannot_access_builder_403(self):
        """Респондент при попытке открыть конструктор получает ошибку 403."""
        self.client.login(username='resp_user', password='Password123!')
        response = self.client.get(f'/{self.survey1.pk}/builder/')
        self.assertEqual(response.status_code, 403)
        self.assertTemplateUsed(response, '403.html')

    def test_author_cannot_edit_foreign_survey_403(self):
        """Автор не может редактировать чужой опрос (403 Forbidden)."""
        self.client.login(username='author2', password='Password123!')
        response = self.client.get(f'/{self.survey1.pk}/builder/')
        self.assertEqual(response.status_code, 403)
        self.assertTemplateUsed(response, '403.html')

    def test_author_can_access_own_builder(self):
        """Автор успешно открывает конструктор своего опроса."""
        self.client.login(username='author1', password='Password123!')
        response = self.client.get(f'/{self.survey1.pk}/builder/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'surveys/builder.html')

    def test_author_publish_survey(self):
        """Автор может опубликовать опрос с вопросами."""
        Question.objects.create(survey=self.survey1, text='Первый вопрос', qtype='rating')
        self.client.login(username='author1', password='Password123!')
        response = self.client.post(f'/{self.survey1.pk}/publish/', {'status': 'published'}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.survey1.refresh_from_db()
        self.assertEqual(self.survey1.status, 'published')

    def test_author_delete_survey(self):
        """Автор может удалить свой опрос."""
        self.client.login(username='author1', password='Password123!')
        response = self.client.post(f'/{self.survey1.pk}/delete/', follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Survey.objects.filter(pk=self.survey1.pk).exists())

    def test_other_author_cannot_delete_foreign_survey_403(self):
        """Посторонний автор получает 403 при попытке удалить чужой опрос (защита от IDOR)."""
        self.client.login(username='author2', password='Password123!')
        response = self.client.post(f'/{self.survey1.pk}/delete/')
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Survey.objects.filter(pk=self.survey1.pk).exists())

    def test_other_author_cannot_publish_foreign_survey_403(self):
        """Посторонний автор получает 403 при попытке изменить статус чужого опроса."""
        self.client.login(username='author2', password='Password123!')
        response = self.client.post(f'/{self.survey1.pk}/publish/', {'status': 'published'})
        self.assertEqual(response.status_code, 403)



class SurveyRespondingAndResultTests(TestCase):
    """
    Тесты прохождения опроса и формирования карточки-итога (Этап 5):
    - Доступность интерфейса прохождения для опубликованного опроса
    - Сохранение ответов разных типов (свайп, эмоция, звёзды, выбор, текст)
    - Защита от повторного прохождения (редирект на карточку-итог)
    - Корректность расчёта сравнительной статистики
    """

    def setUp(self):
        self.client = Client()

        self.author = User.objects.create_user(username='author_runner', password='Password123!')
        self.author.profile.role = 'author'
        self.author.profile.save()

        self.respondent = User.objects.create_user(username='resp_runner', password='Password123!')
        self.respondent.profile.role = 'respondent'
        self.respondent.profile.save()

        self.survey = Survey.objects.create(
            author=self.author,
            title='Опрос для проверки прохождения',
            status='published'
        )

        self.q_swipe = Question.objects.create(survey=self.survey, text='Свайп', qtype='swipe', order=0)
        self.q_emotion = Question.objects.create(survey=self.survey, text='Эмоция', qtype='emotion', order=1)
        self.q_rating = Question.objects.create(survey=self.survey, text='Рейтинг', qtype='rating', order=2)
        self.q_single = Question.objects.create(survey=self.survey, text='Один выбор', qtype='single', order=3)
        self.choice1 = Choice.objects.create(question=self.q_single, text='Вариант А')
        self.choice2 = Choice.objects.create(question=self.q_single, text='Вариант Б')

    def test_open_survey_run_page(self):
        """Респондент может открыть опубликованный опрос."""
        self.client.login(username='resp_runner', password='Password123!')
        response = self.client.get(f'/{self.survey.pk}/respond/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'surveys/survey_run.html')
        self.assertContains(response, self.survey.title)

    def test_submit_answers_and_view_result(self):
        """Отправка ответов через POST и проверка формирования Response и Answer."""
        self.client.login(username='resp_runner', password='Password123!')

        answers_payload = {
            'answers': {
                str(self.q_swipe.id): 1.0,
                str(self.q_emotion.id): 3.5,
                str(self.q_rating.id): 5.0,
                str(self.q_single.id): self.choice1.id,
            }
        }

        import json
        response = self.client.post(
            f'/{self.survey.pk}/respond/',
            data=json.dumps(answers_payload),
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'ok')
        self.assertIn(f'/{self.survey.pk}/result/', data['redirect_url'])

        # Проверяем записи в базе данных
        self.assertTrue(Response.objects.filter(survey=self.survey, respondent=self.respondent).exists())
        user_resp = Response.objects.get(survey=self.survey, respondent=self.respondent)
        self.assertEqual(user_resp.answers.count(), 4)

        # Проверяем открытие страницы результата
        result_page = self.client.get(f'/{self.survey.pk}/result/')
        self.assertEqual(result_page.status_code, 200)
        self.assertTemplateUsed(result_page, 'surveys/survey_result.html')
        self.assertContains(result_page, 'Опрос успешно пройден')

    def test_cannot_respond_twice_redirects_to_result(self):
        """При попытке пройти опрос повторно пользователя перенаправляет на страницу с его итогом."""
        Response.objects.create(survey=self.survey, respondent=self.respondent)
        self.client.login(username='resp_runner', password='Password123!')

        response = self.client.get(f'/{self.survey.pk}/respond/', follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'surveys/survey_result.html')


class SurveyStatisticsTests(TestCase):
    """
    Тесты раздела статистики и экспорта в CSV (Этап 6):
    - Доступ автора к статистике своего опроса
    - Защита (403) от просмотра статистики чужого опроса другим автором
    - Защита (403) респондента от входа в статистику
    - Корректность генерации и скачивания CSV файла
    - Корректность расчёта аналитических показателей
    """

    def setUp(self):
        self.client = Client()

        self.author = User.objects.create_user(username='stats_author', password='Password123!')
        self.author.profile.role = 'author'
        self.author.profile.save()

        self.other_author = User.objects.create_user(username='other_author', password='Password123!')
        self.other_author.profile.role = 'author'
        self.other_author.profile.save()

        self.respondent = User.objects.create_user(username='stats_resp', password='Password123!')
        self.respondent.profile.role = 'respondent'
        self.respondent.profile.save()

        self.survey = Survey.objects.create(
            author=self.author,
            title='Опрос для проверки статистики',
            status='published'
        )

        self.q1 = Question.objects.create(survey=self.survey, text='Оценка темы', qtype='rating', order=0)
        self.q2 = Question.objects.create(survey=self.survey, text='Свайп темы', qtype='swipe', order=1)

        # Создаём ответ респондента
        self.response_obj = Response.objects.create(survey=self.survey, respondent=self.respondent)
        Answer.objects.create(response=self.response_obj, question=self.q1, number=5.0)
        Answer.objects.create(response=self.response_obj, question=self.q2, number=1.0)

    def test_author_can_access_own_stats(self):
        """Автор успешно открывает статистику своего опроса."""
        self.client.login(username='stats_author', password='Password123!')
        response = self.client.get(f'/{self.survey.pk}/stats/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'surveys/stats.html')
        self.assertContains(response, 'Всего ответов')
        self.assertContains(response, 'Завершенность')

    def test_other_author_cannot_access_stats_403(self):
        """Посторонний автор получает 403 при попытке открыть чужую аналитику."""
        self.client.login(username='other_author', password='Password123!')
        response = self.client.get(f'/{self.survey.pk}/stats/')
        self.assertEqual(response.status_code, 403)
        self.assertTemplateUsed(response, '403.html')

    def test_respondent_cannot_access_stats_403(self):
        """Респондент получает 403 при попытке открыть статистику."""
        self.client.login(username='stats_resp', password='Password123!')
        response = self.client.get(f'/{self.survey.pk}/stats/')
        self.assertEqual(response.status_code, 403)
        self.assertTemplateUsed(response, '403.html')

    def test_export_csv_download(self):
        """Автор может выгрузить результаты опроса в формате CSV."""
        self.client.login(username='stats_author', password='Password123!')
        response = self.client.get(f'/{self.survey.pk}/export/csv/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/csv', response['Content-Type'])
        self.assertIn(f'lumi_survey_{self.survey.id}_results.csv', response['Content-Disposition'])
        content = response.content.decode('utf-8-sig')
        self.assertIn('ID ответа', content)
        self.assertIn('stats_resp', content)
        self.assertIn('Оценка темы', content)

    def test_other_author_cannot_export_csv_403(self):
        """Посторонний автор получает 403 при попытке экспорта чужих данных."""
        self.client.login(username='other_author', password='Password123!')
        response = self.client.get(f'/{self.survey.pk}/export/csv/')
        self.assertEqual(response.status_code, 403)


class SurveyAIGeneratorTests(TestCase):
    """
    Тесты модуля AI-генератора опросов (Этап 7):
    - Определение категории по ключевым словам (учеба, сервис, мероприятие, общий)
    - Формирование структуры из 6 вопросов со всеми типами
    - Создание опроса через представление survey_create_with_ai
    - Генерация вопросов через AJAX эндпоинт survey_ai_generate
    - Защита (403): респондент не может вызывать AI-генератор
    """

    def setUp(self):
        self.client = Client()

        self.author = User.objects.create_user(username='ai_author', password='Password123!')
        self.author.profile.role = 'author'
        self.author.profile.save()

        self.respondent = User.objects.create_user(username='ai_resp', password='Password123!')
        self.respondent.profile.role = 'respondent'
        self.respondent.profile.save()

        self.survey = Survey.objects.create(author=self.author, title='Черновик для AI', status='draft')

    def test_ai_detect_category_and_generate_survey(self):
        """Проверяем функцию generate_survey на выбор правильных категорий и 6 типов вопросов."""
        from surveys.ai import generate_survey, detect_category

        # Проверка категорий
        self.assertEqual(detect_category('Курс по Django и Python для студентов'), 'education')
        self.assertEqual(detect_category('Качество доставки и обслуживания клиентов магазина'), 'service')
        self.assertEqual(detect_category('Митап разработчиков и конференция 2026'), 'event')
        self.assertEqual(detect_category('Случайная абстрактная тема без ключевых слов'), 'general')

        # Проверка генерации 6 вопросов
        result = generate_survey('Изучение веб-разработки на Django')
        self.assertEqual(len(result['questions']), 6)
        types = [q['qtype'] for q in result['questions']]
        self.assertIn('swipe', types)
        self.assertIn('emotion', types)
        self.assertIn('rating', types)
        self.assertIn('single', types)
        self.assertIn('multiple', types)
        self.assertIn('text', types)

    def test_survey_create_with_ai_view(self):
        """Автор создаёт новый опрос через форму 'Создать с помощью AI'."""
        self.client.login(username='ai_author', password='Password123!')
        response = self.client.post('/create/ai/', {'topic': 'Школа английского языка'}, follow=True)
        self.assertEqual(response.status_code, 200)

        # Проверяем, что опрос создан в базе с 6 вопросами
        created_survey = Survey.objects.filter(author=self.author).exclude(pk=self.survey.pk).first()
        self.assertIsNotNone(created_survey)
        self.assertEqual(created_survey.questions.count(), 6)
        self.assertEqual(created_survey.status, 'draft')

    def test_survey_ai_generate_ajax_endpoint(self):
        """Автор вызывает AJAX генератор внутри конструктора."""
        self.client.login(username='ai_author', password='Password123!')

        import json
        payload = {'topic': 'Мобильное приложение доставки', 'save_to_db': True}
        response = self.client.post(
            f'/{self.survey.pk}/ai-generate/',
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'ok')
        self.assertEqual(len(data['data']['questions']), 6)

        # Проверяем, что опрос обновился в базе
        self.survey.refresh_from_db()
        self.assertEqual(self.survey.questions.count(), 6)

    def test_respondent_cannot_call_ai_generator_403(self):
        """Респондент не может вызывать эндпоинт AI-генерации."""
        self.client.login(username='ai_resp', password='Password123!')

        import json
        response = self.client.post(
            f'/{self.survey.pk}/ai-generate/',
            data=json.dumps({'topic': 'Тест'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 403)


class SurveyRestApiTests(TestCase):
    """
    Автоматизированные тесты для REST API (DRF) — Этап 8:
    - Без авторизации API возвращает 401/403
    - Получение данных профиля через /api/me/
    - Получение списка опубликованных опросов /api/surveys/
    - Детальная структура опроса /api/surveys/<id>/
    - Отправка ответов респондентом /api/surveys/<id>/respond/
    - Защита от повторной отправки через API (400 Bad Request)
    - Статистика /api/surveys/<id>/stats/ доступна только автору (403 остальным)
    """

    def setUp(self):
        self.client = Client()

        self.author = User.objects.create_user(username='api_author', password='Password123!')
        self.author.profile.role = 'author'
        self.author.profile.save()

        self.other_user = User.objects.create_user(username='api_other', password='Password123!')
        self.other_user.profile.role = 'respondent'
        self.other_user.profile.save()

        self.survey = Survey.objects.create(
            author=self.author,
            title='Тестовый API опрос',
            status='published'
        )
        self.q1 = Question.objects.create(survey=self.survey, text='Вопрос API', qtype='rating', order=0)
        self.q2 = Question.objects.create(survey=self.survey, text='Выбор API', qtype='single', order=1)
        self.choice = Choice.objects.create(question=self.q2, text='Опция 1')

    def test_anonymous_access_denied_401_or_403(self):
        """Анонимный запрос без авторизации отклоняется."""
        response = self.client.get('/api/surveys/')
        self.assertIn(response.status_code, [401, 403])

    def test_get_current_user_profile(self):
        """Авторизованный пользователь получает данные профиля через /api/me/."""
        self.client.login(username='api_author', password='Password123!')
        response = self.client.get('/api/me/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['username'], 'api_author')
        self.assertEqual(data['role'], 'author')

    def test_get_published_surveys_list(self):
        """Авторизованный пользователь получает список опубликованных опросов."""
        self.client.login(username='api_other', password='Password123!')
        response = self.client.get('/api/surveys/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsInstance(data, list)
        self.assertTrue(any(s['id'] == self.survey.id for s in data))

    def test_get_survey_detail_with_questions(self):
        """Получение подробной структуры опроса с вопросами и вариантами."""
        self.client.login(username='api_other', password='Password123!')
        response = self.client.get(f'/api/surveys/{self.survey.id}/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['title'], self.survey.title)
        self.assertEqual(len(data['questions']), 2)

    def test_respond_via_api_and_prevent_duplicate(self):
        """Респондент отправляет ответы через API, повторная попытка блокируется."""
        self.client.login(username='api_other', password='Password123!')

        import json
        payload = {
            'answers': [
                {'question_id': self.q1.id, 'number': 4.0},
                {'question_id': self.q2.id, 'choice_id': self.choice.id}
            ]
        }

        # Первый успешный ответ (201 Created)
        response = self.client.post(
            f'/api/surveys/{self.survey.id}/respond/',
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['status'], 'ok')
        self.assertTrue(Response.objects.filter(survey=self.survey, respondent=self.other_user).exists())

        # Повторный ответ отклоняется (400 Bad Request)
        repeat_response = self.client.post(
            f'/api/surveys/{self.survey.id}/respond/',
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(repeat_response.status_code, 400)

    def test_author_can_access_stats_via_api(self):
        """Автор опроса успешно получает статистику через /api/surveys/<id>/stats/."""
        self.client.login(username='api_author', password='Password123!')
        response = self.client.get(f'/api/surveys/{self.survey.id}/stats/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['survey_id'], self.survey.id)
        self.assertIn('total_responses', data)
        self.assertIn('completion_rate', data)
        self.assertIn('questions_analysis', data)

    def test_other_user_forbidden_from_stats_via_api_403(self):
        """Посторонний пользователь получает 403 Forbidden при запросе статистики через API."""
        self.client.login(username='api_other', password='Password123!')
        response = self.client.get(f'/api/surveys/{self.survey.id}/stats/')
        self.assertEqual(response.status_code, 403)





