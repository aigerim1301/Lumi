"""
Команда Django для генерации демонстрационных данных (seed_demo).
Создаёт администратора, автора, респондентов, 2 опроса со всеми типами вопросов
и реалистичные ответы для красивой статистики и диаграмм.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from accounts.models import Profile
from surveys.models import Survey, Question, Choice, Response, Answer


class Command(BaseCommand):
    help = 'Заполняет базу данных демонстрационными пользователями, опросами и ответами.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('Начало заполнения демонстрационных данных Lumi...'))

        # 1. Создание суперпользователя / администратора
        admin_user, created = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@lumi.local',
                'first_name': 'Администратор',
                'last_name': 'Lumi',
                'is_staff': True,
                'is_superuser': True,
            }
        )
        admin_user.set_password('AdminPassword123!')
        admin_user.save()
        admin_profile, _ = Profile.objects.get_or_create(user=admin_user)
        admin_profile.role = 'author'
        admin_profile.save()
        self.stdout.write(self.style.SUCCESS('Администратор создан: admin / AdminPassword123!'))

        # 2. Создание демонстрационного автора (Александр К.)
        author_user, created = User.objects.get_or_create(
            username='author',
            defaults={
                'email': 'author@lumi.local',
                'first_name': 'Александр',
                'last_name': 'Коваленко',
            }
        )
        author_user.set_password('AuthorPassword123!')
        author_user.save()
        author_profile, _ = Profile.objects.get_or_create(user=author_user)
        author_profile.role = 'author'
        author_profile.dark_theme = False
        author_profile.notifications = True
        author_profile.save()
        self.stdout.write(self.style.SUCCESS('Автор создан: author / AuthorPassword123!'))

        # 3. Создание основного демо-респондента (Елена С.)
        main_resp_user, created = User.objects.get_or_create(
            username='respondent',
            defaults={
                'email': 'respondent@lumi.local',
                'first_name': 'Елена',
                'last_name': 'Смирнова',
            }
        )
        main_resp_user.set_password('RespondentPassword123!')
        main_resp_user.save()
        main_resp_profile, _ = Profile.objects.get_or_create(user=main_resp_user)
        main_resp_profile.role = 'respondent'
        main_resp_profile.save()
        self.stdout.write(self.style.SUCCESS('Респондент создан: respondent / RespondentPassword123!'))

        # Дополнительные респонденты для наполнения статистики
        sample_respondents = [
            ('anna', 'Анна', 'Иванова'),
            ('ivan', 'Иван', 'Петров'),
            ('maria', 'Мария', 'Сидорова'),
            ('dmitry', 'Дмитрий', 'Морозов'),
            ('olga', 'Ольга', 'Васильева'),
        ]
        created_respondents = [main_resp_user]
        for u_name, f_name, l_name in sample_respondents:
            u, _ = User.objects.get_or_create(
                username=u_name,
                defaults={'first_name': f_name, 'last_name': l_name, 'email': f'{u_name}@mail.test'}
            )
            u.set_password('UserPass123!')
            u.save()
            p, _ = Profile.objects.get_or_create(user=u)
            p.role = 'respondent'
            p.save()
            created_respondents.append(u)

        # 4. Создание Опроса 1: «Опрос удовлетворённости курсом Python и Django»
        survey1, _ = Survey.objects.get_or_create(
            author=author_user,
            title='Опрос удовлетворённости курсом Python и Django',
            defaults={
                'description': 'Поделитесь своими впечатлениями от обучения, чтобы помочь нам сделать программу ещё лучше.',
                'status': 'published',
            }
        )

        # Удаляем старые вопросы для чистоты перезапуска сида
        survey1.questions.all().delete()

        # Вопрос 1: Свайп
        q1_1 = Question.objects.create(
            survey=survey1,
            text='Было ли вам легко усваивать материал первых модулей?',
            qtype='swipe',
            order=0
        )

        # Вопрос 2: Термометр эмоций (-4 .. +4)
        q1_2 = Question.objects.create(
            survey=survey1,
            text='Термометр настроения: насколько уверенно вы чувствуете себя при работе с Django?',
            qtype='emotion',
            order=1
        )

        # Вопрос 3: Звёздный рейтинг (1..5)
        q1_3 = Question.objects.create(
            survey=survey1,
            text='Оцените понятность объяснений наставника от 1 до 5 звёзд',
            qtype='rating',
            order=2
        )

        # Вопрос 4: Один вариант
        q1_4 = Question.objects.create(
            survey=survey1,
            text='Какой архитектурный паттерн вам показался самым удобным?',
            qtype='single',
            order=3
        )
        c1_4_1 = Choice.objects.create(question=q1_4, text='Django MVT (Model-View-Template)')
        c1_4_2 = Choice.objects.create(question=q1_4, text='REST API + Frontend')
        c1_4_3 = Choice.objects.create(question=q1_4, text='Микросервисы')

        # Вопрос 5: Множественный выбор
        q1_5 = Question.objects.create(
            survey=survey1,
            text='Какие темы вы хотите разобрать дополнительно?',
            qtype='multiple',
            order=4
        )
        c1_5_1 = Choice.objects.create(question=q1_5, text='Тестирование и автотесты')
        c1_5_2 = Choice.objects.create(question=q1_5, text='Оптимизация запросов к базе (select_related)')
        c1_5_3 = Choice.objects.create(question=q1_5, text='Деплой на боевой сервер')

        # Вопрос 6: Открытый текст
        q1_6 = Question.objects.create(
            survey=survey1,
            text='Что в обучении понравилось больше всего?',
            qtype='text',
            order=5
        )

        # 5. Создание ответов респондентов на Опрос 1
        survey1.responses.all().delete()

        demo_answers_data = [
            (created_respondents[0], 1, 3.0, 5.0, c1_4_1, [c1_5_1, c1_5_3], 'Очень крутой игровой интерфейс и понятный код!'),
            (created_respondents[1], 1, 4.0, 5.0, c1_4_1, [c1_5_1], 'Отличная подача материала и много практики.'),
            (created_respondents[2], -1, 1.0, 4.0, c1_4_2, [c1_5_2, c1_5_3], 'Хочется больше разборов сложных SQL запросов.'),
            (created_respondents[3], 1, 2.0, 4.0, c1_4_1, [c1_5_3], 'Понравился блок про Django REST Framework.'),
            (created_respondents[4], 1, 4.0, 5.0, c1_4_2, [c1_5_1, c1_5_2], 'Шикарный проект, всё разложено по полочкам!'),
        ]

        for resp_user, swipe_val, emotion_val, rating_val, choice_val, multi_choices, text_val in demo_answers_data:
            resp = Response.objects.create(survey=survey1, respondent=resp_user)
            # Ответ на свайп
            Answer.objects.create(response=resp, question=q1_1, number=swipe_val)
            # Ответ на эмоции
            Answer.objects.create(response=resp, question=q1_2, number=emotion_val)
            # Ответ на рейтинг
            Answer.objects.create(response=resp, question=q1_3, number=rating_val)
            # Ответ на один выбор
            Answer.objects.create(response=resp, question=q1_4, choice=choice_val)
            # Ответы на мультивыбор
            for m_choice in multi_choices:
                Answer.objects.create(response=resp, question=q1_5, choice=m_choice)
            # Ответ на текст
            Answer.objects.create(response=resp, question=q1_6, text=text_val)

        # 6. Создание Опроса 2: «Обратная связь: дизайн и механики Lumi»
        survey2, _ = Survey.objects.get_or_create(
            author=author_user,
            title='Обратная связь: дизайн и механики Lumi',
            defaults={
                'description': 'Оцените цветовую гамму «Цифровой шалфей и терракота» и интерактивные свайпы.',
                'status': 'published',
            }
        )
        survey2.questions.all().delete()

        q2_1 = Question.objects.create(
            survey=survey2,
            text='Оцените цветовую гамму платформы (шалфей, терракота, лаванда)',
            qtype='rating',
            order=0
        )
        q2_2 = Question.objects.create(
            survey=survey2,
            text='Термометр комфорта: насколько удобна адаптивность для смартфона?',
            qtype='emotion',
            order=1
        )
        q2_3 = Question.objects.create(
            survey=survey2,
            text='Какая тема оформления вам ближе?',
            qtype='single',
            order=2
        )
        c2_3_1 = Choice.objects.create(question=q2_3, text='Светлая (тёплый бежевый #F7F5F0)')
        c2_3_2 = Choice.objects.create(question=q2_3, text='Тёмная (глубокий шалфейный #141A18)')

        # Добавим ответы на Опрос 2
        survey2.responses.all().delete()
        for resp_user in created_respondents[1:4]:
            resp = Response.objects.create(survey=survey2, respondent=resp_user)
            Answer.objects.create(response=resp, question=q2_1, number=5.0)
            Answer.objects.create(response=resp, question=q2_2, number=3.5)
            Answer.objects.create(response=resp, question=q2_3, choice=c2_3_1)

        self.stdout.write(self.style.SUCCESS('2 опроса и реалистичные ответы успешно сгенерированы!'))
        self.stdout.write(self.style.SUCCESS('Готово! Команда seed_demo выполнена успешно.'))
