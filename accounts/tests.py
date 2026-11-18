from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
import json


class AccountsAuthTests(TestCase):
    """
    Автоматизированные тесты для приложения accounts (Этап 3):
    - Регистрация с выбором роли (автор / респондент)
    - Валидация совпадения паролей
    - Авторизация (вход) и выход
    - Ограничение доступа к профилю только для вошедших пользователей
    - Обновление настроек (тёмная тема, уведомления)
    - Экспорт персональных данных в JSON
    """

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='existing_user',
            password='Password123!',
            first_name='Алексей'
        )
        self.user.profile.role = 'author'
        self.user.profile.save()

    def test_registration_with_author_role(self):
        """Проверка регистрации пользователя с ролью 'author'."""
        response = self.client.post(reverse('register'), {
            'username': 'new_author',
            'first_name': 'Сергей',
            'email': 'author@test.local',
            'role': 'author',
            'password': 'SecurePassword123!',
            'password_confirm': 'SecurePassword123!',
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(User.objects.filter(username='new_author').exists())
        new_user = User.objects.get(username='new_author')
        self.assertEqual(new_user.profile.role, 'author')
        # Проверяем, что пользователь сразу авторизован
        self.assertEqual(int(self.client.session['_auth_user_id']), new_user.pk)

    def test_registration_with_respondent_role(self):
        """Проверка регистрации пользователя с ролью 'respondent'."""
        response = self.client.post(reverse('register'), {
            'username': 'new_resp',
            'role': 'respondent',
            'password': 'SecurePassword123!',
            'password_confirm': 'SecurePassword123!',
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        new_user = User.objects.get(username='new_resp')
        self.assertEqual(new_user.profile.role, 'respondent')

    def test_registration_password_mismatch(self):
        """Проверка ошибки несовпадения паролей при регистрации."""
        response = self.client.post(reverse('register'), {
            'username': 'fail_user',
            'role': 'respondent',
            'password': 'SecurePassword123!',
            'password_confirm': 'DifferentPassword123!',
        })
        self.assertFalse(User.objects.filter(username='fail_user').exists())
        self.assertFormError(response.context['form'], 'password_confirm', 'Пароли не совпадают.')

    def test_login_success(self):
        """Проверка успешного входа."""
        response = self.client.post(reverse('login'), {
            'username': 'existing_user',
            'password': 'Password123!',
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(int(self.client.session['_auth_user_id']), self.user.pk)

    def test_login_invalid_password(self):
        """Проверка ошибки при неверном пароле."""
        response = self.client.post(reverse('login'), {
            'username': 'existing_user',
            'password': 'WrongPassword!',
        })
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_logout(self):
        """Проверка выхода из системы."""
        self.client.login(username='existing_user', password='Password123!')
        response = self.client.post(reverse('logout'), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_profile_requires_login(self):
        """Анонимный пользователь при попытке открыть профиль перенаправляется на логин."""
        response = self.client.get(reverse('profile'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_profile_settings_update(self):
        """Авторизованный пользователь может обновлять свои настройки и тёмную тему."""
        self.client.login(username='existing_user', password='Password123!')
        response = self.client.post(reverse('profile'), {
            'first_name': 'Александр',
            'last_name': 'Ковалев',
            'email': 'alex@lumi.test',
            'dark_theme': True,
            'notifications': False,
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Александр')
        self.assertEqual(self.user.profile.dark_theme, True)
        self.assertEqual(self.user.profile.notifications, False)

    def test_export_data_json(self):
        """Проверка выгрузки персональных данных в формате JSON."""
        self.client.login(username='existing_user', password='Password123!')
        response = self.client.get(reverse('profile_export'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json; charset=utf-8')
        data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(data['username'], 'existing_user')
        self.assertEqual(data['role'], 'author')
