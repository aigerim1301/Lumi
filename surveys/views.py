"""
Представления приложения surveys: управление опросами, конструктор, публикация и удаление.
"""
import json
import csv
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.contrib import messages
from django.http import JsonResponse, HttpResponseForbidden, HttpResponse
from django.db.models import Count
from django.db import transaction
from django.urls import reverse
from .models import Survey, Question, Choice, Response, Answer
from .permissions import author_required
from .stats import calculate_respondent_summary, calculate_survey_statistics
from .ai import generate_survey


def survey_list(request):
    """
    Главная страница / список опросов.
    - Для гостей: приветственная страница Lumi с описанием и кнопками входа.
    - Автору показывает его опросы со статусами (Черновик, Опубликован, Завершён) и счётчиками ответов.
    - Респонденту показывает опубликованные опросы с отметкой, пройден ли опрос.
    """
    if not request.user.is_authenticated:
        return render(request, 'home.html')

    user = request.user
    profile = getattr(user, 'profile', None)
    is_author = (profile and profile.role == 'author') or user.is_staff

    if is_author:
        # Автор видит свои опросы
        status_filter = request.GET.get('status', 'all')
        surveys_qs = Survey.objects.filter(author=user) if not user.is_staff else Survey.objects.all()

        total_count = surveys_qs.count()
        draft_count = surveys_qs.filter(status='draft').count()
        published_count = surveys_qs.filter(status='published').count()
        closed_count = surveys_qs.filter(status='closed').count()

        if status_filter == 'draft':
            surveys_qs = surveys_qs.filter(status='draft')
        elif status_filter == 'published':
            surveys_qs = surveys_qs.filter(status='published')
        elif status_filter == 'closed':
            surveys_qs = surveys_qs.filter(status='closed')

        return render(request, 'surveys/survey_list_author.html', {
            'surveys': surveys_qs,
            'status_filter': status_filter,
            'total_count': total_count,
            'draft_count': draft_count,
            'published_count': published_count,
            'closed_count': closed_count,
            'is_author': True,
        })
    else:
        # Респондент видит только опубликованные опросы
        published_surveys = Survey.objects.filter(status='published').prefetch_related('responses')

        # Список ID опросов, которые этот пользователь уже прошел
        completed_survey_ids = set(
            Response.objects.filter(respondent=user).values_list('survey_id', flat=True)
        )

        surveys_data = []
        for s in published_surveys:
            surveys_data.append({
                'survey': s,
                'is_completed': s.id in completed_survey_ids,
                'question_count': s.questions.count(),
            })

        return render(request, 'surveys/survey_list_respondent.html', {
            'surveys_data': surveys_data,
            'is_author': False,
        })


@author_required
def survey_create(request):
    """
    Создание нового опроса в статусе черновика.
    Сразу перенаправляет автора в интерактивный конструктор.
    """
    if request.method == 'POST':
        title = request.POST.get('title', 'Новый опрос Lumi').strip()
        description = request.POST.get('description', '').strip()
        survey = Survey.objects.create(
            author=request.user,
            title=title if title else 'Новый опрос Lumi',
            description=description,
            status='draft'
        )
        messages.success(request, f'Опрос «{survey.title}» создан! Добавьте в него вопросы.')
        return redirect('survey_builder', pk=survey.pk)

    # При обычном клике создаем черновик и сразу открываем конструктор
    survey = Survey.objects.create(
        author=request.user,
        title='Новый опрос Lumi',
        description='',
        status='draft'
    )
    # Создаем стартовый приветственный вопрос
    Question.objects.create(
        survey=survey,
        text='Как вы оцениваете наши услуги?',
        qtype='rating',
        order=0
    )
    return redirect('survey_builder', pk=survey.pk)


@author_required
def survey_create_with_ai(request):
    """
    Быстрое создание опроса с помощью AI по одной фразе:
    - Принимает тему опроса
    - Генерирует структуру из 6 вопросов со всеми игровыми механиками
    - Создает опрос и перенаправляет в конструктор для редактирования.
    """
    if request.method == 'POST':
        topic = request.POST.get('topic', '').strip()
        if not topic:
            messages.warning(request, 'Пожалуйста, введите тему для генерации опроса.')
            return redirect('survey_list')

        # Генерируем опрос через модуль surveys/ai.py
        ai_data = generate_survey(topic)

        with transaction.atomic():
            survey = Survey.objects.create(
                author=request.user,
                title=ai_data['title'],
                description=ai_data['description'],
                status='draft'
            )

            for q_info in ai_data['questions']:
                q_obj = Question.objects.create(
                    survey=survey,
                    text=q_info['text'],
                    qtype=q_info['qtype'],
                    order=q_info['order']
                )
                for c_text in q_info.get('choices', []):
                    Choice.objects.create(question=q_obj, text=c_text)

        messages.success(
            request,
            f'✨ AI-конструктор сгенерировал 6 вопросов по теме «{topic}» ({ai_data["category_name"]})! Вы можете отредактировать любые пункты.'
        )
        return redirect('survey_builder', pk=survey.pk)

    return redirect('survey_list')


@author_required
def survey_ai_generate(request, pk):
    """
    AJAX-эндпоинт для генерации вопросов прямо внутри открытого конструктора опроса:
    - Вызывает generate_survey(topic)
    - Возвращает 6 готовых вопросов клиенту в формате JSON для мгновенной подстановки.
    """
    survey = get_object_or_404(Survey, pk=pk)

    if survey.author != request.user and not request.user.is_staff:
        raise PermissionDenied("Вы не можете изменять чужой опрос.")

    if request.method == 'POST':
        try:
            payload = json.loads(request.body)
            topic = payload.get('topic', '').strip()
            if not topic:
                return JsonResponse({'status': 'error', 'message': 'Введите тему для генерации опроса.'}, status=400)

            ai_data = generate_survey(topic)

            # Если запрошено сохранение в базу прямо сейчас
            save_to_db = payload.get('save_to_db', True)
            if save_to_db:
                with transaction.atomic():
                    # Обновляем заголовок, если он был стандартным
                    if survey.title == 'Новый опрос Lumi' or not survey.title:
                        survey.title = ai_data['title']
                    if not survey.description:
                        survey.description = ai_data['description']
                    survey.save()

                    # Очищаем старые вопросы и сохраняем 6 сгенерированных
                    survey.questions.all().delete()
                    for q_info in ai_data['questions']:
                        q_obj = Question.objects.create(
                            survey=survey,
                            text=q_info['text'],
                            qtype=q_info['qtype'],
                            order=q_info['order']
                        )
                        for c_text in q_info.get('choices', []):
                            Choice.objects.create(question=q_obj, text=c_text)

            return JsonResponse({
                'status': 'ok',
                'data': ai_data,
                'message': f'Сгенерировано 6 вопросов по категории «{ai_data["category_name"]}»!'
            })
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

    return JsonResponse({'status': 'error', 'message': 'Метод не поддерживается.'}, status=405)


@author_required
def survey_builder(request, pk):
    """
    Интерактивный конструктор опроса:
    - редактирование названия и описания
    - добавление, редактирование и удаление блоков-вопросов
    - настройка вариантов для вопросов с выбором (single/multiple)
    - публикация и смена статусов
    Проверяет права: только автор опроса (или администратор) может его редактировать.
    """
    survey = get_object_or_404(Survey, pk=pk)

    # Строгий контроль доступа: автор может редактировать только СВОИ опросы!
    if survey.author != request.user and not request.user.is_staff:
        raise PermissionDenied("Вы не можете редактировать чужой опрос.")

    # Обработка асинхронного сохранения всей структуры из JS конструктора
    if request.headers.get('x-requested-with') == 'XMLHttpRequest' and request.method == 'POST':
        try:
            data = json.loads(request.body)
            # Обновление основных полей опроса
            if 'title' in data and data['title'].strip():
                survey.title = data['title'].strip()
            if 'description' in data:
                survey.description = data['description'].strip()
            if 'status' in data and data['status'] in dict(Survey.STATUS_CHOICES):
                survey.status = data['status']
            survey.save()

            # Обновление структуры вопросов
            if 'questions' in data:
                # Очищаем старые вопросы и создаем заново по актуальному состоянию конструктора
                survey.questions.all().delete()
                for q_idx, q_data in enumerate(data['questions']):
                    q_text = q_data.get('text', '').strip()
                    if not q_text:
                        q_text = f'Вопрос {q_idx + 1}'
                    q_type = q_data.get('qtype', 'single')

                    question = Question.objects.create(
                        survey=survey,
                        text=q_text,
                        qtype=q_type,
                        order=q_idx
                    )

                    # Если тип с выбором вариантов — сохраняем варианты
                    if q_type in ('single', 'multiple'):
                        choices = q_data.get('choices', [])
                        for c_text in choices:
                            c_clean = str(c_text).strip()
                            if c_clean:
                                Choice.objects.create(question=question, text=c_clean)

            return JsonResponse({'status': 'ok', 'message': 'Опрос успешно сохранён!'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

    # Обычный POST запрос формы сохранения метаданных опроса
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        status = request.POST.get('status', survey.status)

        if title:
            survey.title = title
        survey.description = description
        if status in dict(Survey.STATUS_CHOICES):
            survey.status = status
        survey.save()
        messages.success(request, 'Параметры опроса сохранены!')
        return redirect('survey_builder', pk=survey.pk)

    # Список существующих вопросов
    questions = survey.questions.prefetch_related('choices').all()

    return render(request, 'surveys/builder.html', {
        'survey': survey,
        'questions': questions,
        'question_types': Question.QUESTION_TYPES,
    })


@author_required
def survey_publish(request, pk):
    """
    Публикация опроса или изменение его статуса (Черновик / Опубликован / Завершён).
    """
    survey = get_object_or_404(Survey, pk=pk)

    if survey.author != request.user and not request.user.is_staff:
        raise PermissionDenied("Вы не можете изменять статус чужого опроса.")

    if request.method == 'POST':
        new_status = request.POST.get('status', 'published')

        if new_status == 'published':
            if survey.questions.count() == 0:
                messages.error(request, 'Нельзя опубликовать пустой опрос. Добавьте хотя бы один вопрос.')
                return redirect('survey_builder', pk=survey.pk)
            survey.status = 'published'
            survey.save()
            messages.success(request, f'Опрос «{survey.title}» успешно опубликован и доступен респондентам!')
        elif new_status == 'closed':
            survey.status = 'closed'
            survey.save()
            messages.info(request, f'Опрос «{survey.title}» переведён в статус «Завершён».')
        elif new_status == 'draft':
            survey.status = 'draft'
            survey.save()
            messages.info(request, f'Опрос «{survey.title}» возвращён в черновики.')

    return redirect('survey_list')


@author_required
def survey_delete(request, pk):
    """
    Удаление опроса. Разрешено только автору этого опроса или администратору.
    """
    survey = get_object_or_404(Survey, pk=pk)

    if survey.author != request.user and not request.user.is_staff:
        raise PermissionDenied("Вы не можете удалить чужой опрос.")

    if request.method == 'POST':
        survey_title = survey.title
        survey.delete()
        messages.success(request, f'Опрос «{survey_title}» успешно удалён.')
        return redirect('survey_list')

    return render(request, 'surveys/survey_confirm_delete.html', {'survey': survey})


@author_required
def survey_add_question(request, pk):
    """Быстрое добавление нового вопроса в опрос."""
    survey = get_object_or_404(Survey, pk=pk)
    if survey.author != request.user and not request.user.is_staff:
        raise PermissionDenied()

    if request.method == 'POST':
        qtype = request.POST.get('qtype', 'single')
        text = request.POST.get('text', 'Новый вопрос').strip()
        new_order = survey.questions.count()

        q = Question.objects.create(
            survey=survey,
            text=text if text else 'Новый вопрос',
            qtype=qtype,
            order=new_order
        )

        # Если это выбор, добавим два варианта по умолчанию
        if qtype in ('single', 'multiple'):
            Choice.objects.create(question=q, text='Вариант 1')
            Choice.objects.create(question=q, text='Вариант 2')

        messages.success(request, 'Вопрос добавлен!')

    return redirect('survey_builder', pk=survey.pk)


@author_required
def survey_delete_question(request, pk, q_pk):
    """Удаление вопроса из опроса."""
    survey = get_object_or_404(Survey, pk=pk)
    if survey.author != request.user and not request.user.is_staff:
        raise PermissionDenied()

    question = get_object_or_404(Question, pk=q_pk, survey=survey)
    if request.method == 'POST':
        question.delete()
        messages.info(request, 'Вопрос удалён.')

    return redirect('survey_builder', pk=survey.pk)


@login_required
def survey_respond(request, pk):
    """
    Интерактивное прохождение опроса (по одному вопросу на экран):
    - Свайп-карточки (влево/вправо с анимацией и кнопками)
    - Термометр настроения / эмоций (-4..+4 с динамическим цветом и смайликами)
    - Звёздный рейтинг (1-5)
    - Одиночный и множественный выбор
    - Текстовый ввод
    - Проверка: каждый респондент может пройти опрос только 1 раз.
    """
    survey = get_object_or_404(Survey, pk=pk)

    # Проверка статуса опроса
    is_author_or_staff = (survey.author == request.user) or request.user.is_staff
    if survey.status != 'published' and not is_author_or_staff:
        messages.warning(request, 'Этот опрос пока недоступен для прохождения (находится в черновиках или завершён).')
        return redirect('survey_list')

    # Проверяем, проходил ли пользователь этот опрос ранее
    existing_response = Response.objects.filter(survey=survey, respondent=request.user).first()
    if existing_response:
        messages.info(request, 'Вы уже прошли этот опрос! Вот ваши результаты и сравнение с участниками.')
        return redirect('survey_result', pk=survey.pk)

    questions = survey.questions.prefetch_related('choices').all()
    if not questions.exists():
        messages.warning(request, 'В этом опросе пока нет вопросов.')
        return redirect('survey_list')

    # Обработка сохранения ответов (через AJAX JSON)
    if request.method == 'POST':
        try:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':
                payload = json.loads(request.body)
            else:
                payload = request.POST

            answers_data = payload.get('answers', {})

            with transaction.atomic():
                response_obj = Response.objects.create(
                    survey=survey,
                    respondent=request.user
                )

                for q in questions:
                    q_key = str(q.id)
                    q_val = answers_data.get(q_key)

                    if q_val is None:
                        continue

                    if q.qtype == 'rating':
                        try:
                            val = float(q_val)
                            Answer.objects.create(response=response_obj, question=q, number=val)
                        except (ValueError, TypeError):
                            pass

                    elif q.qtype == 'emotion':
                        try:
                            val = float(q_val)
                            Answer.objects.create(response=response_obj, question=q, number=val)
                        except (ValueError, TypeError):
                            pass

                    elif q.qtype == 'swipe':
                        try:
                            val = float(q_val) # -1.0 или 1.0
                            Answer.objects.create(response=response_obj, question=q, number=val)
                        except (ValueError, TypeError):
                            pass

                    elif q.qtype == 'single':
                        try:
                            choice_obj = Choice.objects.filter(id=int(q_val), question=q).first()
                            if choice_obj:
                                Answer.objects.create(response=response_obj, question=q, choice=choice_obj)
                        except (ValueError, TypeError):
                            pass

                    elif q.qtype == 'multiple':
                        # Список ID выбранных вариантов
                        if isinstance(q_val, list):
                            for cid in q_val:
                                choice_obj = Choice.objects.filter(id=int(cid), question=q).first()
                                if choice_obj:
                                    Answer.objects.create(response=response_obj, question=q, choice=choice_obj)

                    elif q.qtype == 'text':
                        text_val = str(q_val).strip()
                        Answer.objects.create(response=response_obj, question=q, text=text_val)

            redirect_url = reverse('survey_result', args=[survey.pk])
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'status': 'ok', 'redirect_url': redirect_url})
            return redirect('survey_result', pk=survey.pk)

        except Exception as e:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
            messages.error(request, f'Ошибка при сохранении ответов: {e}')

    return render(request, 'surveys/survey_run.html', {
        'survey': survey,
        'questions': questions,
        'total_questions': questions.count(),
    })


@login_required
def survey_result(request, pk):
    """
    Мгновенная карточка-итог для респондента после завершения опроса:
    - Показывает: «Вы ответили так же, как X% участников»
    - Сравнение со средним баллом, преобладающими эмоциями и выбором большинства.
    """
    survey = get_object_or_404(Survey, pk=pk)

    # Рассчитываем сравнительную статистику для пользователя
    summary_data = calculate_respondent_summary(survey, request.user)

    if not summary_data:
        # Если пользователь еще не проходил этот опрос
        return redirect('survey_respond', pk=survey.pk)

    return render(request, 'surveys/survey_result.html', summary_data)


@author_required
def survey_stats(request, pk):
    """
    Экран «Статистика» опроса:
    - Плитки «Всего ответов» и «Завершённость»
    - Круговая диаграмма распределения (Chart.js)
    - Столбчатый график «Ответы по дням» (Chart.js)
    - Развернутая статистика по каждому вопросу
    - Кнопка выгрузки в CSV
    Доступно только автору этого опроса или администратору.
    """
    survey = get_object_or_404(Survey, pk=pk)

    if survey.author != request.user and not request.user.is_staff:
        raise PermissionDenied("Статистика доступна только автору этого опроса.")

    stats_data = calculate_survey_statistics(survey)

    # Список всех опросов автора для быстрого переключения в шапке статистики
    author_surveys = Survey.objects.filter(author=request.user) if not request.user.is_staff else Survey.objects.all()
    stats_data['author_surveys'] = author_surveys

    return render(request, 'surveys/stats.html', stats_data)


@author_required
def survey_export_csv(request, pk):
    """
    Экспорт всех ответов опроса в CSV-файл.
    Использует кодировку UTF-8 с BOM (utf-8-sig) для корректного отображения
    русских букв в Microsoft Excel на Windows.
    """
    survey = get_object_or_404(Survey, pk=pk)

    if survey.author != request.user and not request.user.is_staff:
        raise PermissionDenied("Экспорт доступен только автору этого опроса.")

    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    filename = f"lumi_survey_{survey.id}_results.csv"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    writer = csv.writer(response, delimiter=';')
    # Заголовки таблицы
    writer.writerow([
        'ID ответа',
        'Имя респондента',
        'Логин респондента',
        'Дата и время',
        'Порядковый номер вопроса',
        'Текст вопроса',
        'Тип вопроса',
        'Ответ (вариант / текст / число)'
    ])

    responses = survey.responses.select_related('respondent').prefetch_related('answers__question', 'answers__choice').all()

    for resp in responses:
        resp_user = resp.respondent
        user_name = resp_user.get_full_name() or resp_user.username
        resp_date = resp.created_at.strftime('%d.%m.%Y %H:%M:%S')

        for ans in resp.answers.all():
            q = ans.question
            ans_val = ''
            if q.qtype in ('single', 'multiple') and ans.choice:
                ans_val = ans.choice.text
            elif q.qtype == 'rating' and ans.number is not None:
                ans_val = f"{int(ans.number)} из 5 ★"
            elif q.qtype == 'emotion' and ans.number is not None:
                ans_val = f"{ans.number:+.1f}°C"
            elif q.qtype == 'swipe' and ans.number is not None:
                ans_val = 'Свайп вправо (Да / Легко)' if ans.number > 0 else 'Свайп влево (Нет / Трудно)'
            elif q.qtype == 'text':
                ans_val = ans.text

            writer.writerow([
                resp.id,
                user_name,
                resp_user.username,
                resp_date,
                q.order + 1,
                q.text,
                q.get_qtype_display(),
                ans_val
            ])

    return response


@login_required
def stats_summary(request):
    """
    Главная страница раздела статистики:
    - Если передан параметр ?survey=ID, открывает статистику этого опроса.
    - Иначе находит первый опрос автора и открывает его статистику,
      либо отображает обзорный список доступных для анализа опросов.
    """
    user = request.user
    profile = getattr(user, 'profile', None)
    is_author = (profile and profile.role == 'author') or user.is_staff

    if not is_author:
        messages.info(request, 'Раздел аналитики и статистики доступен только авторам опросов.')
        return redirect('survey_list')

    survey_id = request.GET.get('survey')
    if survey_id:
        return redirect('survey_stats', pk=survey_id)

    author_surveys = Survey.objects.filter(author=user) if not user.is_staff else Survey.objects.all()

    first_survey = author_surveys.first()
    if first_survey:
        return redirect('survey_stats', pk=first_survey.pk)

    return render(request, 'surveys/stats_overview.html', {
        'surveys': author_surveys,
    })
