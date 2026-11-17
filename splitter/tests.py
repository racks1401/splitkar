from decimal import Decimal
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from .models import ExpenseGroup, Membership, Expense, ExpenseShare
from .services import split_equally, group_balances


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

        # user2 tries to access add expense page
        response = self.client.get(reverse('expense_create', args=[group.id]))
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


class ExpensesTestCase(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(username='ravi', password='Password123!')
        self.user2 = User.objects.create_user(username='aman', password='Password123!')
        self.user3 = User.objects.create_user(username='sneha', password='Password123!')
        self.outsider = User.objects.create_user(username='outsider', password='Password123!')

        self.group = ExpenseGroup.objects.create(name='Room 204', created_by=self.user1)
        Membership.objects.create(group=self.group, user=self.user1)
        Membership.objects.create(group=self.group, user=self.user2)
        Membership.objects.create(group=self.group, user=self.user3)

    def test_split_equally_rounding_and_sum(self):
        # 100 split among 3 users with ravi as payer
        shares = split_equally(Decimal("100"), [self.user1, self.user2, self.user3], self.user1)
        self.assertEqual(shares[self.user1], Decimal("33.34"))
        self.assertEqual(shares[self.user2], Decimal("33.33"))
        self.assertEqual(shares[self.user3], Decimal("33.33"))
        self.assertEqual(sum(shares.values()), Decimal("100.00"))

    def test_expense_zero_amount_or_non_member_payer_rejected(self):
        self.client.login(username='ravi', password='Password123!')

        # 1. Amount 0 should be rejected
        response_zero = self.client.post(
            reverse('expense_create', args=[self.group.id]),
            {
                'title': 'Free Snack',
                'amount': '0.00',
                'paid_by': self.user1.id,
                'date': '2026-11-17',
                'participants': [self.user1.id, self.user2.id],
            },
        )
        self.assertEqual(response_zero.status_code, 200)
        self.assertFormError(response_zero.context['form'], 'amount', "Amount must be greater than 0.")
        self.assertEqual(Expense.objects.count(), 0)

        # 2. Non-member payer should be rejected
        response_non_member = self.client.post(
            reverse('expense_create', args=[self.group.id]),
            {
                'title': 'Dinner',
                'amount': '150.00',
                'paid_by': self.outsider.id,
                'date': '2026-11-17',
                'participants': [self.user1.id, self.user2.id],
            },
        )
        self.assertEqual(response_non_member.status_code, 200)
        self.assertTrue(response_non_member.context['form'].has_error('paid_by'))
        self.assertEqual(Expense.objects.count(), 0)

    def test_create_expense_atomic_save_and_display(self):
        self.client.login(username='ravi', password='Password123!')

        response = self.client.post(
            reverse('expense_create', args=[self.group.id]),
            {
                'title': 'Hostel Wifi',
                'amount': '100.00',
                'paid_by': self.user1.id,
                'date': '2026-11-17',
                'participants': [self.user1.id, self.user2.id, self.user3.id],
            },
            follow=True,
        )
        self.assertRedirects(response, reverse('group_detail', args=[self.group.id]))

        # Verify Expense created
        expense = Expense.objects.get(title='Hostel Wifi')
        self.assertEqual(expense.amount, Decimal('100.00'))
        self.assertEqual(expense.paid_by, self.user1)

        # Verify ExpenseShare rows created
        shares = expense.shares.all()
        self.assertEqual(shares.count(), 3)
        self.assertEqual(sum(s.share_amount for s in shares), Decimal('100.00'))

        # Verify expense appears in group detail response
        self.assertContains(response, 'Hostel Wifi')
        self.assertContains(response, '₹100.00')


class BalancesTestCase(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(username='ravi', password='Password123!')
        self.user2 = User.objects.create_user(username='aman', password='Password123!')
        self.user3 = User.objects.create_user(username='sneha', password='Password123!')

        self.group = ExpenseGroup.objects.create(name='Room 204', created_by=self.user1)
        Membership.objects.create(group=self.group, user=self.user1)
        Membership.objects.create(group=self.group, user=self.user2)
        Membership.objects.create(group=self.group, user=self.user3)

    def test_empty_group_balances_zero(self):
        balances = group_balances(self.group)
        self.assertEqual(balances[self.user1], Decimal('0.00'))
        self.assertEqual(balances[self.user2], Decimal('0.00'))
        self.assertEqual(balances[self.user3], Decimal('0.00'))
        self.assertEqual(sum(balances.values()), Decimal('0.00'))

    def test_balances_match_spec_example_table_and_sum_to_zero(self):
        # Ravi pays 100 for Ravi, Aman, and Sneha
        expense = Expense.objects.create(
            group=self.group,
            title='Dinner',
            amount=Decimal('100.00'),
            paid_by=self.user1,
            created_by=self.user1,
        )
        shares = split_equally(expense.amount, [self.user1, self.user2, self.user3], self.user1)
        for user, share_amount in shares.items():
            ExpenseShare.objects.create(
                expense=expense,
                user=user,
                share_amount=share_amount,
            )

        balances = group_balances(self.group)

        # Spec Example Table:
        # Ravi: Paid 100.00, Share 33.34, Balance +66.66
        # Aman: Paid 0.00, Share 33.33, Balance -33.33
        # Sneha: Paid 0.00, Share 33.33, Balance -33.33
        self.assertEqual(balances[self.user1], Decimal('66.66'))
        self.assertEqual(balances[self.user2], Decimal('-33.33'))
        self.assertEqual(balances[self.user3], Decimal('-33.33'))

        # Balances sum to 0
        self.assertEqual(sum(balances.values()), Decimal('0.00'))

    def test_balances_displayed_in_group_detail_and_dashboard(self):
        # Setup the 100 expense paid by ravi
        expense = Expense.objects.create(
            group=self.group,
            title='Groceries',
            amount=Decimal('100.00'),
            paid_by=self.user1,
            created_by=self.user1,
        )
        shares = split_equally(expense.amount, [self.user1, self.user2, self.user3], self.user1)
        for user, share_amount in shares.items():
            ExpenseShare.objects.create(
                expense=expense,
                user=user,
                share_amount=share_amount,
            )

        # Check group detail page as ravi
        self.client.login(username='ravi', password='Password123!')
        response = self.client.get(reverse('group_detail', args=[self.group.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'gets back ₹66.66')
        self.assertContains(response, 'owes ₹33.33')

        # Check dashboard as ravi (shows gets back in green)
        dash_ravi = self.client.get(reverse('dashboard'))
        self.assertEqual(dash_ravi.status_code, 200)
        self.assertContains(dash_ravi, 'gets back ₹66.66')

        # Check dashboard as aman (shows owes in red)
        self.client.login(username='aman', password='Password123!')
        dash_aman = self.client.get(reverse('dashboard'))
        self.assertEqual(dash_aman.status_code, 200)
        self.assertContains(dash_aman, 'owes ₹33.33')
