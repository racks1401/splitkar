from django.contrib import admin
from .models import ExpenseGroup, Membership, Expense, ExpenseShare


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 1


class ExpenseShareInline(admin.TabularInline):
    model = ExpenseShare
    extra = 1


@admin.register(ExpenseGroup)
class ExpenseGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_by', 'created_at')
    search_fields = ('name',)
    inlines = [MembershipInline]


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ('group', 'user', 'joined_at')
    search_fields = ('group__name', 'user__username')


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ('title', 'group', 'amount', 'paid_by', 'date', 'created_by')
    list_filter = ('group', 'date')
    search_fields = ('title', 'paid_by__username')
    inlines = [ExpenseShareInline]


@admin.register(ExpenseShare)
class ExpenseShareAdmin(admin.ModelAdmin):
    list_display = ('expense', 'user', 'share_amount')
    list_filter = ('expense__group',)
    search_fields = ('user__username', 'expense__title')
