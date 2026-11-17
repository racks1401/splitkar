from decimal import Decimal, ROUND_DOWN
from django.db.models import Sum
from .models import Expense, ExpenseShare


def split_equally(amount, participants, payer):
    """
    Equal split with rounding:
    Divide amount by number of participants and round down to 2 decimal places.
    Whatever paise are left over go one paisa at a time:
    1. First to the payer if the payer is a participant.
    2. Then to the other participants in username order.
    Returns dict mapping user -> Decimal share_amount
    """
    if not isinstance(amount, Decimal):
        amount = Decimal(str(amount))
    amount = amount.quantize(Decimal('0.01'))

    unique_participants = list({p.id: p for p in participants}.values())
    n = len(unique_participants)
    if n == 0:
        raise ValueError("At least one participant is required.")

    base_share = (amount / Decimal(n)).quantize(Decimal('0.01'), rounding=ROUND_DOWN)
    remainder = amount - (base_share * Decimal(n))
    leftover_paise = int((remainder / Decimal('0.01')).to_integral_value())

    payer_participant = next((p for p in unique_participants if p.id == payer.id), None)
    if payer_participant:
        other_participants = sorted(
            [p for p in unique_participants if p.id != payer.id],
            key=lambda u: u.username,
        )
        priority_order = [payer_participant] + other_participants
    else:
        priority_order = sorted(unique_participants, key=lambda u: u.username)

    shares = {p: base_share for p in unique_participants}
    one_paisa = Decimal('0.01')
    for i in range(leftover_paise):
        shares[priority_order[i]] += one_paisa

    return shares


def format_balance(balance):
    """
    Helper to format balance for presentation.
    Positive -> 'gets back ₹X' (green)
    Negative -> 'owes ₹X' (red)
    Zero     -> 'settled' (muted)
    """
    if not isinstance(balance, Decimal):
        balance = Decimal(str(balance))
    balance = balance.quantize(Decimal('0.01'))

    if balance > Decimal('0.00'):
        return {
            'text': f"gets back ₹{balance}",
            'css_class': 'text-success',
            'status': 'positive',
        }
    elif balance < Decimal('0.00'):
        return {
            'text': f"owes ₹{abs(balance)}",
            'css_class': 'text-danger',
            'status': 'negative',
        }
    else:
        return {
            'text': "settled",
            'css_class': 'text-secondary',
            'status': 'settled',
        }


def group_member_summary(group):
    """
    Returns a summary list of dicts for every member of the group:
    user, total paid, total share, balance, and display metadata.
    Uses database aggregation (Sum) and Decimal throughout.
    """
    memberships = group.memberships.select_related('user').order_by('joined_at')

    # Aggregate total amount paid per user in this group
    paid_map = {
        row['paid_by']: Decimal(str(row['total_paid'])).quantize(Decimal('0.01'))
        for row in Expense.objects.filter(group=group)
        .values('paid_by')
        .annotate(total_paid=Sum('amount'))
        if row['total_paid'] is not None
    }

    # Aggregate total share amount per user in this group
    share_map = {
        row['user']: Decimal(str(row['total_share'])).quantize(Decimal('0.01'))
        for row in ExpenseShare.objects.filter(expense__group=group)
        .values('user')
        .annotate(total_share=Sum('share_amount'))
        if row['total_share'] is not None
    }

    zero = Decimal('0.00')
    summary = []
    for membership in memberships:
        user = membership.user
        paid = paid_map.get(user.id, zero)
        share = share_map.get(user.id, zero)
        balance = (paid - share).quantize(Decimal('0.01'))
        display_info = format_balance(balance)
        summary.append({
            'user': user,
            'paid': paid,
            'share': share,
            'balance': balance,
            'display_text': display_info['text'],
            'css_class': display_info['css_class'],
            'status': display_info['status'],
        })

    return summary


def group_balances(group):
    """
    Returns a dict of user -> Decimal balance for every member of the group.
    Balance = total amount of expenses the user paid minus the total of the user's share_amount.
    Members with no expenses get Decimal('0.00').
    """
    summary = group_member_summary(group)
    return {item['user']: item['balance'] for item in summary}
