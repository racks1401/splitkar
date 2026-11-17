from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Count

from .models import ExpenseGroup, Membership
from .forms import ExpenseGroupForm, MemberAddForm


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
    # Retrieve all groups where current user is a member, along with member counts
    groups = (
        ExpenseGroup.objects.filter(memberships__user=request.user)
        .annotate(member_count=Count('memberships', distinct=True))
        .order_by('-created_at')
    )
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
                # Creator becomes a member automatically
                Membership.objects.create(group=group, user=request.user)
            messages.success(request, f"Group '{group.name}' created successfully.")
            return redirect('group_detail', id=group.id)
    else:
        form = ExpenseGroupForm()
    return render(request, 'splitter/group_create.html', {'form': form})


@login_required
def group_detail(request, id):
    # Non-members get 404 so group existence is not revealed
    group = get_object_or_404(ExpenseGroup, id=id, memberships__user=request.user)
    memberships = group.memberships.select_related('user').order_by('joined_at')
    return render(
        request,
        'splitter/group_detail.html',
        {
            'group': group,
            'memberships': memberships,
        },
    )


@login_required
def member_add(request, id):
    # Non-members get 404
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
