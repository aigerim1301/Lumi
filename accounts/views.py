"""
Представления приложения accounts: регистрация с ролью, вход, выход, профиль и экспорт данных.
"""
import json
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.conf import settings
from .forms import RegistrationForm, LoginForm, ProfileSettingsForm
from .models import Profile


def register_view(request):
    """
    Регистрация нового пользователя с выбором роли (автор или респондент).
    После успешного создания аккаунта пользователь сразу авторизуется.
    """
    if request.user.is_authenticated:
        return redirect('survey_list')

    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            email = form.cleaned_data.get('email', '')
            first_name = form.cleaned_data.get('first_name', '')
            role = form.cleaned_data['role']

            # Создаем пользователя Django (пароль хешируется автоматически)
            user = User.objects.create_user(
                username=username,
                password=password,
                email=email,
                first_name=first_name
            )

            # Обновляем роль в автоматически созданном профиле
            profile = user.profile
            profile.role = role
            profile.save()

            # Сразу авторизуем нового пользователя в сессии
            login(request, user)
            role_title = profile.get_role_display().lower()
            messages.success(request, f'Добро пожаловать в Lumi! Ваш аккаунт успешно создан ({role_title}).')
            return redirect('survey_list')
    else:
        form = RegistrationForm()

    return render(request, 'accounts/register.html', {'form': form})


def login_view(request):
    """
    Авторизация пользователя по логину и паролю.
    """
    if request.user.is_authenticated:
        return redirect('survey_list')

    next_url = request.GET.get('next', 'survey_list')

    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']

            # Проверяем подлинность учетных данных
            user = authenticate(request, username=username, password=password)

            if user is not None:
                if user.is_active:
                    login(request, user)
                    greeting_name = user.first_name if user.first_name else user.username
                    messages.success(request, f'С возвращением, {greeting_name}!')
                    return redirect(request.POST.get('next') or next_url or 'survey_list')
                else:
                    messages.error(request, 'Ваш аккаунт деактивирован.')
            else:
                messages.error(request, 'Неверное имя пользователя или пароль. Пожалуйста, попробуйте снова.')
    else:
        form = LoginForm()

    return render(request, 'accounts/login.html', {
        'form': form,
        'next': next_url
    })


def logout_view(request):
    """
    Выход пользователя из системы.
    Поддерживает как POST-запрос формы, так и безопасный переход.
    """
    if request.user.is_authenticated:
        logout(request)
        messages.info(request, 'Вы успешно вышли из системы Lumi.')
    return redirect('login')


@login_required
def profile_view(request):
    """
    Страница профиля и настроек пользователя:
    - отображение имени, роли и аватара
    - переключатели уведомлений и тёмной темы
    - сохранение настроек
    - поддержка мгновенного переключения темы через AJAX
    """
    user = request.user
    profile, _ = Profile.objects.get_or_create(user=user)

    # Обработка быстрого асинхронного переключения темы и языка (AJAX)
    if request.headers.get('x-requested-with') == 'XMLHttpRequest' and request.method == 'POST':
        try:
            data = json.loads(request.body)
            if 'dark_theme' in data:
                profile.dark_theme = bool(data['dark_theme'])
            if 'language' in data and data['language'] in ['ru', 'en', 'ky']:
                profile.language = data['language']
                request.session['django_language'] = data['language']
            profile.save()
            return JsonResponse({
                'status': 'ok',
                'dark_theme': profile.dark_theme,
                'language': profile.language
            })
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

    if request.method == 'POST':
        form = ProfileSettingsForm(request.POST, instance=profile)
        if form.is_valid():
            # Обновляем данные пользователя
            user.first_name = form.cleaned_data.get('first_name', '')
            user.last_name = form.cleaned_data.get('last_name', '')
            user.email = form.cleaned_data.get('email', '')
            user.save()

            # Сохраняем настройки профиля (тёмная тема, язык, уведомления)
            form.save()
            request.session['django_language'] = profile.language
            messages.success(request, 'Настройки профиля успешно сохранены!')
            return redirect('profile')
    else:
        initial_data = {
            'first_name': user.first_name,
            'last_name': user.last_name,
            'email': user.email,
        }
        form = ProfileSettingsForm(instance=profile, initial=initial_data)

    return render(request, 'accounts/profile.html', {
        'user_obj': user,
        'profile': profile,
        'form': form,
    })


@login_required
def export_data_view(request):
    """
    Экспорт персональных данных пользователя в формате JSON (соответствует требованиям защиты данных).
    Выгружает профиль, созданные опросы (для автора) и пройденные опросы (для респондента).
    """
    user = request.user
    profile = user.profile

    user_data = {
        'username': user.username,
        'full_name': f"{user.first_name} {user.last_name}".strip(),
        'email': user.email,
        'role': profile.role,
        'role_title': profile.get_role_display(),
        'dark_theme': profile.dark_theme,
        'language': profile.language,
        'notifications': profile.notifications,
        'date_joined': user.date_joined.isoformat(),
        'surveys_created': [
            {
                'id': s.id,
                'title': s.title,
                'status': s.status,
                'created_at': s.created_at.isoformat(),
                'responses_count': s.responses.count()
            } for s in user.surveys.all()
        ],
        'surveys_completed': [
            {
                'survey_id': r.survey.id,
                'survey_title': r.survey.title,
                'completed_at': r.created_at.isoformat(),
            } for r in user.survey_responses.all()
        ]
    }

    response = HttpResponse(
        json.dumps(user_data, ensure_ascii=False, indent=2),
        content_type='application/json; charset=utf-8'
    )
    response['Content-Disposition'] = f'attachment; filename="lumi_user_data_{user.username}.json"'
    return response
