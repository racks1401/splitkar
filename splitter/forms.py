from decimal import Decimal
from django import forms
from django.contrib.auth.models import User
from django.utils import timezone
from .models import ExpenseGroup, Expense


class ExpenseGroupForm(forms.ModelForm):
    class Meta:
        model = ExpenseGroup
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'e.g. Room 204 or Goa Trip'}),
            'description': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Optional description'}),
        }


class MemberAddForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        label="Username",
        widget=forms.TextInput(attrs={'placeholder': 'Enter exact username'}),
    )

    def __init__(self, *args, group=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.group = group

    def clean_username(self):
        username = self.cleaned_data['username'].strip()
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise forms.ValidationError(f"User '{username}' does not exist.")

        if self.group and self.group.memberships.filter(user=user).exists():
            raise forms.ValidationError(f"'{username}' is already a member of this group.")

        return user


class ExpenseCreateForm(forms.ModelForm):
    participants = forms.ModelMultipleChoiceField(
        queryset=User.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        required=True,
        error_messages={'required': 'At least one participant must be selected.'},
    )

    class Meta:
        model = Expense
        fields = ['title', 'amount', 'paid_by', 'date']
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'e.g. Milk and bread'}),
            'amount': forms.NumberInput(attrs={'step': '0.01', 'min': '0.01', 'placeholder': '0.00'}),
            'date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, group=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.group = group
        if group:
            group_members = User.objects.filter(memberships__group=group).order_by('username')
            self.fields['paid_by'].queryset = group_members
            self.fields['participants'].queryset = group_members
            if not self.is_bound:
                self.fields['participants'].initial = group_members
                self.fields['date'].initial = timezone.localdate()

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount is not None:
            if amount <= Decimal('0'):
                raise forms.ValidationError("Amount must be greater than 0.")
            if amount.as_tuple().exponent < -2:
                raise forms.ValidationError("Amount can have at most 2 decimal places.")
        return amount

    def clean_paid_by(self):
        paid_by = self.cleaned_data.get('paid_by')
        if self.group and paid_by:
            if not self.group.memberships.filter(user=paid_by).exists():
                raise forms.ValidationError("Payer must be a member of this group.")
        return paid_by

    def clean_participants(self):
        participants = self.cleaned_data.get('participants')
        if not participants:
            raise forms.ValidationError("At least one participant must be selected.")
        if self.group:
            for participant in participants:
                if not self.group.memberships.filter(user=participant).exists():
                    raise forms.ValidationError(f"User '{participant.username}' is not a member of this group.")
        return participants
