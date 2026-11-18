"""
Модуль аналитики и расчёта сравнительной статистики для Lumi.
Используется для карточки-итога респондента и аналитических дашбордов.
"""
from collections import defaultdict
from django.db.models import Avg, Count
from django.db.models.functions import TruncDate
from .models import Response, Answer, Question, Choice


def calculate_respondent_summary(survey, user):
    """
    Рассчитывает карточку-итог для конкретного респондента:
    - Общее количество участников
    - Сравнение ответов респондента со средними показателями и мнением большинства («Вы ответили так же, как X% участников»)
    """
    response_obj = Response.objects.filter(survey=survey, respondent=user).first()
    if not response_obj:
        return None

    total_responses = survey.responses.count()
    user_answers = response_obj.answers.select_related('question', 'choice').all()

    # Сгруппируем ответы пользователя по question_id
    answers_by_question = {}
    for ans in user_answers:
        q_id = ans.question_id
        if q_id not in answers_by_question:
            answers_by_question[q_id] = []
        answers_by_question[q_id].append(ans)

    summary_items = []
    same_as_majority_count = 0
    comparable_questions_count = 0

    questions = survey.questions.prefetch_related('choices').all()

    for q in questions:
        q_answers = answers_by_question.get(q.id, [])
        if not q_answers:
            continue

        item = {
            'question_text': q.text,
            'qtype': q.qtype,
            'user_display': '',
            'comparison_text': '',
            'is_majority': False,
        }

        if q.qtype == 'rating':
            comparable_questions_count += 1
            user_val = q_answers[0].number or 0.0
            avg_val = Answer.objects.filter(question=q, number__isnull=False).aggregate(avg=Avg('number'))['avg'] or user_val
            item['user_display'] = f"{int(user_val)} из 5 ★"
            item['avg_display'] = f"{avg_val:.1f} из 5 ★"
            if abs(user_val - avg_val) <= 1.0:
                item['comparison_text'] = f"Близко к среднему значению участников ({avg_val:.1f} ★)"
                same_as_majority_count += 1
            elif user_val > avg_val:
                item['comparison_text'] = f"Выше среднего балла ({avg_val:.1f} ★)"
            else:
                item['comparison_text'] = f"Ниже среднего балла ({avg_val:.1f} ★)"

        elif q.qtype == 'emotion':
            comparable_questions_count += 1
            user_val = q_answers[0].number or 0.0
            avg_val = Answer.objects.filter(question=q, number__isnull=False).aggregate(avg=Avg('number'))['avg'] or user_val
            user_sign = f"+{user_val:.1f}" if user_val > 0 else f"{user_val:.1f}"
            avg_sign = f"+{avg_val:.1f}" if avg_val > 0 else f"{avg_val:.1f}"
            item['user_display'] = f"{user_sign}°C"
            item['avg_display'] = f"{avg_sign}°C"
            if abs(user_val - avg_val) <= 1.5:
                item['comparison_text'] = f"Ваше настроение совпадает со средним по группе ({avg_sign}°C)"
                same_as_majority_count += 1
            elif user_val > avg_val:
                item['comparison_text'] = f"Ваш настрой оптимистичнее среднего ({avg_sign}°C)"
            else:
                item['comparison_text'] = f"Ваша оценка строже средней по группе ({avg_sign}°C)"

        elif q.qtype == 'swipe':
            comparable_questions_count += 1
            user_val = q_answers[0].number or 1.0
            user_choice_is_right = (user_val > 0)
            item['user_display'] = "Свайп вправо (Да / Легко)" if user_choice_is_right else "Свайп влево (Нет / Трудно)"

            total_swipes = Answer.objects.filter(question=q, number__isnull=False).count()
            right_swipes = Answer.objects.filter(question=q, number__gt=0).count()
            right_pct = round((right_swipes / total_swipes * 100)) if total_swipes > 0 else 50
            same_pct = right_pct if user_choice_is_right else (100 - right_pct)

            item['comparison_text'] = f"Так же ответили {same_pct}% участников"
            if same_pct >= 50:
                item['is_majority'] = True
                same_as_majority_count += 1

        elif q.qtype == 'single':
            comparable_questions_count += 1
            chosen_choice = q_answers[0].choice
            if chosen_choice:
                item['user_display'] = chosen_choice.text
                total_q_answers = Answer.objects.filter(question=q, choice__isnull=False).count()
                same_choice_answers = Answer.objects.filter(question=q, choice=chosen_choice).count()
                pct = round((same_choice_answers / total_q_answers * 100)) if total_q_answers > 0 else 100
                item['comparison_text'] = f"{pct}% участников выбрали этот же вариант"
                if pct >= 40:
                    item['is_majority'] = True
                    same_as_majority_count += 1
            else:
                item['user_display'] = "—"

        elif q.qtype == 'multiple':
            choices_texts = [ans.choice.text for ans in q_answers if ans.choice]
            item['user_display'] = ", ".join(choices_texts) if choices_texts else "—"
            item['comparison_text'] = f"Выбрано вариантов: {len(choices_texts)}"

        elif q.qtype == 'text':
            item['user_display'] = q_answers[0].text or "—"
            item['comparison_text'] = "Текстовый отзыв учтён автором"

        summary_items.append(item)

    # Итоговый общий процент сходства с аудиторией
    overall_match_pct = round((same_as_majority_count / comparable_questions_count * 100)) if comparable_questions_count > 0 else 75

    return {
        'survey': survey,
        'response': response_obj,
        'total_responses': total_responses,
        'overall_match_pct': max(10, min(95, overall_match_pct)),
        'summary_items': summary_items,
    }


def calculate_survey_statistics(survey):
    """
    Рассчитывает полную аналитику опроса для страницы «Статистика»:
    - Плитки «Всего ответов» и «Завершённость»
    - Динамику ответов по дням (для столбчатой диаграммы Chart.js)
    - Данные для круговой/пончиковой диаграммы распределения вариантов
    - Анализ по каждому вопросу (средний рейтинг, термометр настроения, свайпы)
    """
    responses_qs = survey.responses.all()
    total_responses = responses_qs.count()
    total_questions = survey.questions.count()

    # Завершённость (% ответивших на все вопросы)
    if total_responses > 0 and total_questions > 0:
        total_expected_answers = total_responses * total_questions
        actual_answers_count = Answer.objects.filter(response__survey=survey).values('response', 'question').distinct().count()
        completion_rate = min(100, round((actual_answers_count / total_expected_answers) * 100))
    else:
        completion_rate = 100 if total_responses > 0 else 0

    # 1. График: Ответы по дням (за последние даты)
    daily_stats = (
        responses_qs.annotate(date=TruncDate('created_at'))
        .values('date')
        .annotate(count=Count('id'))
        .order_by('date')
    )
    days_labels = []
    days_counts = []
    for item in daily_stats:
        # Форматируем дату, например "12 Ноя"
        d = item['date']
        months = ['Янв', 'Фев', 'Мар', 'Апр', 'Май', 'Июн', 'Июл', 'Авг', 'Сен', 'Окт', 'Ноя', 'Дек']
        label = f"{d.day} {months[d.month - 1]}"
        days_labels.append(label)
        days_counts.append(item['count'])

    # Если ответов пока мало, гарантируем непустой график
    if not days_labels and total_responses > 0:
        days_labels = ['Сегодня']
        days_counts = [total_responses]

    # 2. Анализ по каждому вопросу и поиск основного вопроса для круговой диаграммы
    questions = survey.questions.prefetch_related('choices').all()
    questions_analysis = []
    primary_chart_question = None

    for q in questions:
        q_data = {
            'id': q.id,
            'text': q.text,
            'qtype': q.qtype,
            'qtype_display': q.get_qtype_display(),
            'total_answers': 0,
        }

        answers_for_q = Answer.objects.filter(question=q)
        q_data['total_answers'] = answers_for_q.values('response').distinct().count()

        if q.qtype in ('single', 'multiple'):
            choices_stats = []
            labels = []
            counts = []
            for c in q.choices.all():
                c_count = answers_for_q.filter(choice=c).count()
                choices_stats.append({
                    'text': c.text,
                    'count': c_count,
                    'pct': round((c_count / total_responses * 100)) if total_responses > 0 else 0
                })
                labels.append(c.text)
                counts.append(c_count)

            q_data['choices_stats'] = choices_stats
            q_data['chart_labels'] = labels
            q_data['chart_counts'] = counts

            if not primary_chart_question and labels:
                primary_chart_question = {
                    'title': q.text,
                    'labels': labels,
                    'counts': counts,
                }

        elif q.qtype == 'rating':
            avg_rating = answers_for_q.filter(number__isnull=False).aggregate(avg=Avg('number'))['avg'] or 0.0
            q_data['avg_rating'] = round(avg_rating, 1)
            # Распределение по звёздам 1..5
            rating_counts = [answers_for_q.filter(number=i).count() for i in range(1, 6)]
            q_data['rating_counts'] = rating_counts

        elif q.qtype == 'emotion':
            avg_temp = answers_for_q.filter(number__isnull=False).aggregate(avg=Avg('number'))['avg'] or 0.0
            q_data['avg_emotion'] = round(avg_temp, 1)
            q_data['positive_count'] = answers_for_q.filter(number__gt=0).count()
            q_data['neutral_count'] = answers_for_q.filter(number=0).count()
            q_data['negative_count'] = answers_for_q.filter(number__lt=0).count()

        elif q.qtype == 'swipe':
            right_count = answers_for_q.filter(number__gt=0).count()
            left_count = answers_for_q.filter(number__lt=0).count()
            total_swipes = right_count + left_count
            q_data['right_count'] = right_count
            q_data['left_count'] = left_count
            q_data['right_pct'] = round((right_count / total_swipes * 100)) if total_swipes > 0 else 50
            q_data['left_pct'] = 100 - q_data['right_pct']

            if not primary_chart_question:
                primary_chart_question = {
                    'title': q.text,
                    'labels': ['Да / Легко (вправо)', 'Нет / Трудно (влево)'],
                    'counts': [right_count, left_count],
                }

        elif q.qtype == 'text':
            text_answers = answers_for_q.exclude(text='').select_related('response__respondent')[:15]
            q_data['text_answers'] = [
                {
                    'text': a.text,
                    'user': a.response.respondent.get_full_name() or a.response.respondent.username,
                    'date': a.response.created_at.strftime('%d.%m.%Y %H:%M')
                } for a in text_answers
            ]

        questions_analysis.append(q_data)

    # Если не нашли вопрос с выбором для круговой диаграммы, сделаем заглушку
    if not primary_chart_question:
        primary_chart_question = {
            'title': 'Распределение активности',
            'labels': ['Завершено', 'В процессе'],
            'counts': [total_responses, 0],
        }

    return {
        'survey': survey,
        'total_responses': total_responses,
        'completion_rate': completion_rate,
        'days_labels': days_labels,
        'days_counts': days_counts,
        'primary_chart': primary_chart_question,
        'questions_analysis': questions_analysis,
    }
