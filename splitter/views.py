from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Count

from .models import ExpenseGroup, Membership, Expense, ExpenseShare
from .forms import ExpenseGroupForm, MemberAddForm, ExpenseCreateForm
from .services import split_equally, group_balances, group_member_summary, format_balance


def signup(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('dashboard')
    else:
        form = UserCreationForm()
    return render(request, 'registration/signup.html', {'form': form})


@login_required
def dashboard(request):
    # Filter by id so the member count includes every member, not just me
    my_group_ids = Membership.objects.filter(user=request.user).values('group_id')
    groups = (
        ExpenseGroup.objects.filter(id__in=my_group_ids)
        .annotate(member_count=Count('memberships', distinct=True))
        .order_by('-created_at')
    )
    # Determine user's balance in each group
    zero = Decimal('0.00')
    for group in groups:
        balances = group_balances(group)
        user_balance = balances.get(request.user, zero)
        group.my_balance_display = format_balance(user_balance)

    return render(request, 'splitter/dashboard.html', {'groups': groups})


@login_required
def group_create(request):
    if request.method == 'POST':
        form = ExpenseGroupForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                group = form.save(commit=False)
                group.created_by = request.user
                group.save()
                Membership.objects.create(group=group, user=request.user)
            messages.success(request, f"Group '{group.name}' created successfully.")
            return redirect('group_detail', id=group.id)
    else:
        form = ExpenseGroupForm()
    return render(request, 'splitter/group_create.html', {'form': form})


@login_required
def group_detail(request, id):
    group = get_object_or_404(ExpenseGroup, id=id, memberships__user=request.user)
    memberships = group.memberships.select_related('user').order_by('joined_at')
    expenses = group.expenses.select_related('paid_by')
    member_balances = group_member_summary(group)

    return render(
        request,
        'splitter/group_detail.html',
        {
            'group': group,
            'memberships': memberships,
            'expenses': expenses,
            'member_balances': member_balances,
        },
    )


@login_required
def member_add(request, id):
    group = get_object_or_404(ExpenseGroup, id=id, memberships__user=request.user)
    if request.method == 'POST':
        form = MemberAddForm(request.POST, group=group)
        if form.is_valid():
            user_to_add = form.cleaned_data['username']
            Membership.objects.create(group=group, user=user_to_add)
            messages.success(request, f"'{user_to_add.username}' added to '{group.name}'.")
            return redirect('group_detail', id=group.id)
    else:
        form = MemberAddForm(group=group)
    return render(request, 'splitter/member_add.html', {'group': group, 'form': form})


@login_required
def expense_create(request, id):
    group = get_object_or_404(ExpenseGroup, id=id, memberships__user=request.user)
    if request.method == 'POST':
        form = ExpenseCreateForm(request.POST, group=group)
        if form.is_valid():
            with transaction.atomic():
                expense = form.save(commit=False)
                expense.group = group
                expense.created_by = request.user
                expense.save()

                shares = split_equally(
                    amount=expense.amount,
                    participants=form.cleaned_data['participants'],
                    payer=expense.paid_by,
                )

                for participant, share_amount in shares.items():
                    ExpenseShare.objects.create(
                        expense=expense,
                        user=participant,
                        share_amount=share_amount,
                    )

            messages.success(request, f"Expense '{expense.title}' added successfully.")
            return redirect('group_detail', id=group.id)
    else:
        form = ExpenseCreateForm(group=group)

    return render(request, 'splitter/expense_create.html', {'group': group, 'form': form})
