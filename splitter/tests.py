from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from .models import ExpenseGroup, Membership


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
        self.assertTrue(User.objects.filter(username='testuser').exists())
        self.assertEqual(response.context['user'].username, 'testuser')
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


class GroupsTestCase(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(username='ravi', password='Password123!')
        self.user2 = User.objects.create_user(username='aman', password='Password123!')
        self.user3 = User.objects.create_user(username='sneha', password='Password123!')

    def test_creating_group_makes_creator_member(self):
        self.client.login(username='ravi', password='Password123!')
        response = self.client.post(
            reverse('group_create'),
            {'name': 'Room 204', 'description': 'Hostel Room'},
            follow=True,
        )
        group = ExpenseGroup.objects.get(name='Room 204')
        self.assertRedirects(response, reverse('group_detail', args=[group.id]))
        self.assertEqual(group.created_by, self.user1)
        self.assertTrue(Membership.objects.filter(group=group, user=self.user1).exists())

    def test_non_member_gets_404_on_group_page(self):
        # Create group by user1
        group = ExpenseGroup.objects.create(name='Goa Trip', created_by=self.user1)
        Membership.objects.create(group=group, user=self.user1)

        # user2 (not a member) tries to view group detail
        self.client.login(username='aman', password='Password123!')
        response = self.client.get(reverse('group_detail', args=[group.id]))
        self.assertEqual(response.status_code, 404)

        # user2 tries to access add member page
        response = self.client.get(reverse('member_add', args=[group.id]))
        self.assertEqual(response.status_code, 404)

    def test_adding_unknown_user_or_existing_member_shows_error_and_adds_nothing(self):
        group = ExpenseGroup.objects.create(name='Room 204', created_by=self.user1)
        Membership.objects.create(group=group, user=self.user1)

        self.client.login(username='ravi', password='Password123!')

        # 1. Add non-existent user
        response = self.client.post(
            reverse('member_add', args=[group.id]),
            {'username': 'ghost_user'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context['form'], 'username', "User 'ghost_user' does not exist.")
        self.assertEqual(group.memberships.count(), 1)

        # 2. Add user who is already a member
        response = self.client.post(
            reverse('member_add', args=[group.id]),
            {'username': 'ravi'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context['form'], 'username', "'ravi' is already a member of this group.")
        self.assertEqual(group.memberships.count(), 1)

        # 3. Add valid existing user who is not yet a member
        response = self.client.post(
            reverse('member_add', args=[group.id]),
            {'username': 'aman'},
            follow=True,
        )
        self.assertRedirects(response, reverse('group_detail', args=[group.id]))
        self.assertEqual(group.memberships.count(), 2)
        self.assertTrue(group.memberships.filter(user=self.user2).exists())
