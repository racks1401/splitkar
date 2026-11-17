from decimal import Decimal, ROUND_DOWN


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
