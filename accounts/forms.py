"""
Формы приложения accounts: регистрация с выбором роли, вход и редактирование профиля.
"""
from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from .models import Profile


class RegistrationForm(forms.Form):
    """
    Форма регистрации нового пользователя Lumi с явным выбором роли:
    - Автор (создаёт опросы и смотрит аналитику)
    - Респондент (проходит опросы)
    """
    ROLE_CHOICES = (
        ('respondent', 'Респондент (хочу проходить опросы)'),
        ('author', 'Автор (хочу создавать опросы и изучать статистику)'),
    )

    username = forms.CharField(
        label='Имя пользователя (логин)',
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Например, alex_k',
            'autocomplete': 'username'
        })
    )
    first_name = forms.CharField(
        label='Имя',
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Александр'
        })
    )
    email = forms.EmailField(
        label='Электронная почта',
        required=False,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'alex@example.com'
        })
    )
    role = forms.ChoiceField(
        label='Выберите вашу роль в Lumi',
        choices=ROLE_CHOICES,
        initial='respondent',
        widget=forms.RadioSelect(attrs={'class': 'role-radio-input'})
    )
    password = forms.CharField(
        label='Пароль',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Минимум 8 символов'
        })
    )
    password_confirm = forms.CharField(
        label='Повторите пароль',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Повторите введённый пароль'
        })
    )

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError('Пользователь с таким логином уже существует. Выберите другой.')
        return username

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        password_confirm = cleaned_data.get('password_confirm')

        if password and password_confirm:
            if password != password_confirm:
                self.add_error('password_confirm', 'Пароли не совпадают.')
            else:
                # Проверяем пароль через стандартные валидаторы Django (длина, простота)
                try:
                    validate_password(password)
                except ValidationError as error:
                    self.add_error('password', error)

        return cleaned_data


class LoginForm(forms.Form):
    """
    Форма авторизации (входа в систему).
    """
    username = forms.CharField(
        label='Имя пользователя (логин)',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Введите ваш логин',
            'autocomplete': 'username'
        })
    )
    password = forms.CharField(
        label='Пароль',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Введите пароль',
            'autocomplete': 'current-password'
        })
    )


class ProfileSettingsForm(forms.ModelForm):
    """
    Форма настроек профиля: персональные данные, тёмная тема и уведомления.
    """
    first_name = forms.CharField(
        label='Имя',
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    last_name = forms.CharField(
        label='Фамилия',
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    email = forms.EmailField(
        label='Электронная почта',
        required=False,
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )

    class Meta:
        model = Profile
        fields = ['dark_theme', 'notifications']
        labels = {
            'dark_theme': 'Тёмная тема',
            'notifications': 'Уведомления',
        }
        widgets = {
            'dark_theme': forms.CheckboxInput(attrs={'class': 'toggle-input', 'id': 'darkThemeToggle'}),
            'notifications': forms.CheckboxInput(attrs={'class': 'toggle-input', 'id': 'notificationsToggle'}),
        }
