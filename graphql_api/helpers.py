from datetime import date
from uuid import UUID

from apps.members.models import Member, MembershipPlan
from apps.payments.models import FeeRecord
from .types import MemberType, MembershipPlanType, FeeRecordType


def plan_to_type(plan: MembershipPlan) -> MembershipPlanType:
    return MembershipPlanType(
        id=plan.id,
        plan_name=plan.plan_name,
        description=plan.description,
        price=float(plan.price),
        duration_months=plan.duration_months,
        duration_days=plan.duration_days,
        is_active=plan.is_active,
        created_at=plan.created_at,
    )


def member_to_type(
    m: Member,
    paid_member_ids: set | None = None,
) -> MemberType:
    today = date.today()
    if paid_member_ids is None:
        current_month = today.replace(day=1)
        paid_member_ids = set(
            FeeRecord.objects.filter(month=current_month, status='Paid').values_list(
                'member_id', flat=True
            )
        )
    days_left = (m.expiry_date - today).days
    return MemberType(
        id=m.id,
        full_name=m.full_name,
        father_name=m.father_name,
        phone_number=m.phone_number,
        cnic=m.cnic,
        address=m.address,
        notes=m.notes,
        join_date=m.join_date,
        start_date=m.join_date,
        expiry_date=m.expiry_date,
        status=m.status,
        is_active=m.is_active,
        membership_plan=plan_to_type(m.membership_plan),
        paid_status='Paid' if m.id in paid_member_ids else 'Unpaid',
        days_until_expiry=days_left,
    )


def fee_to_type(r: FeeRecord, paid_member_ids: set | None = None) -> FeeRecordType:
    return FeeRecordType(
        id=r.id,
        amount=float(r.amount),
        month=r.month,
        payment_date=r.payment_date,
        status=r.status,
        member=member_to_type(r.member, paid_member_ids),
    )
