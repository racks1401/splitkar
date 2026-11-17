from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User


class AccountsTestCase(TestCase):
    def test_signup_creates_user_and_logs_them_in(self):
        response = self.client.post(
            reverse('signup'),
            {
                'username': 'testuser',
                'password1': 'StrongPass123!',
                'password2': 'StrongPass123!',
            },
            follow=True,
        )
        # Verify user was created in database
        self.assertTrue(User.objects.filter(username='testuser').exists())
        # Verify user is logged in
        self.assertEqual(response.context['user'].username, 'testuser')
        # Verify redirected to dashboard
        self.assertRedirects(response, reverse('dashboard'))

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse('dashboard'))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('dashboard')}")

    def test_login_and_logout(self):
        User.objects.create_user(username='testuser', password='StrongPass123!')
        
        # Test Login
        login_response = self.client.post(
            reverse('login'),
            {'username': 'testuser', 'password': 'StrongPass123!'},
            follow=True,
        )
        self.assertRedirects(login_response, reverse('dashboard'))
        self.assertTrue(login_response.context['user'].is_authenticated)

        # Test Logout (POST only in Django 5)
        logout_response = self.client.post(reverse('logout'), follow=True)
        self.assertRedirects(logout_response, reverse('login'))
        self.assertFalse(logout_response.context['user'].is_authenticated)
