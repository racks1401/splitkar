from django.contrib import admin
from .models import ExpenseGroup, Membership


class MembershipInline(admin.TabularInline):
    model = Membership
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
