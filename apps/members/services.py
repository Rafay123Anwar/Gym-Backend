"""Membership lifecycle: expiry calculation and automatic status sync."""
from datetime import date, timedelta
from calendar import monthrange

from django.db.models import Q

from .models import Member, MembershipPlan


def add_months(start: date, months: int) -> date:
    """Add calendar months to a date, clamping day to last day of target month."""
    month = start.month - 1 + months
    year = start.year + month // 12
    month = month % 12 + 1
    last_day = monthrange(year, month)[1]
    day = min(start.day, last_day)
    return date(year, month, day)


def calculate_expiry_date(start_date: date, plan: MembershipPlan) -> date:
    """Expiry = start_date + plan duration (days take precedence over months)."""
    if plan.duration_days:
        return start_date + timedelta(days=plan.duration_days)
    return add_months(start_date, plan.duration_months)


def is_membership_valid(member: Member, on_date: date | None = None) -> bool:
    on_date = on_date or date.today()
    return member.expiry_date >= on_date


def expire_overdue_members() -> int:
    """
    Mark members whose validity period has ended.
    Returns count of members updated.
    """
    today = date.today()
    overdue = Member.objects.filter(
        expiry_date__lt=today,
    ).exclude(status='Expired')

    count = overdue.update(status='Expired', is_active=False)
    return count


def sync_member_on_read(member: Member) -> Member:
    """Ensure a single member row reflects expiry before returning to clients."""
    today = date.today()
    if member.expiry_date < today and member.status != 'Expired':
        member.status = 'Expired'
        member.is_active = False
        member.save(update_fields=['status', 'is_active', 'updated_at'])
    return member


def get_expiry_alerts(within_days: int = 7) -> list[dict]:
    """Members expiring within N days (not yet expired)."""
    today = date.today()
    end = today + timedelta(days=within_days)
    members = Member.objects.filter(
        expiry_date__gte=today,
        expiry_date__lte=end,
        status='Active',
        is_active=True,
    ).order_by('expiry_date')

    alerts = []
    for m in members:
        days_left = (m.expiry_date - today).days
        if days_left == 0:
            level = 'today'
            message = f'{m.full_name} membership expires today'
        elif days_left <= 3:
            level = '3_days'
            message = f'{m.full_name} membership expires in {days_left} day{"s" if days_left != 1 else ""}'
        else:
            level = '7_days'
            message = f'{m.full_name} membership expires in {days_left} days'
        alerts.append({
            'member_id': m.id,
            'member_name': m.full_name,
            'expiry_date': m.expiry_date,
            'days_remaining': days_left,
            'level': level,
            'message': message,
        })
    return alerts
