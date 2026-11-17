from django import forms
from django.contrib.auth.models import User
from .models import ExpenseGroup


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
