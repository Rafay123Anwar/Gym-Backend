import typing
import strawberry # type: ignore[import]
import re
from uuid import UUID
from datetime import date

from django.utils import timezone

from .types import MemberType, FeeRecordType, MembershipPlanType, GymSettingsType
from .helpers import member_to_type, plan_to_type
from apps.members.models import Member, MembershipPlan, MembershipActivity
from apps.members.services import calculate_expiry_date, expire_overdue_members
from apps.payments.models import FeeRecord
from apps.dashboard.models import GymSettings


def validate_pakistani_phone(phone: str) -> str:
    # Remove all non-digit chars
    digits = re.sub(r"\D", "", phone)

    # +923XXXXXXXXX
    if digits.startswith("92") and len(digits) == 12:
        normalized = digits

    # 03XXXXXXXXX
    elif digits.startswith("03") and len(digits) == 11:
        normalized = "92" + digits[1:]

    # 3XXXXXXXXX
    elif digits.startswith("3") and len(digits) == 10:
        normalized = "92" + digits

    else:
        raise ValueError(
            "Invalid Pakistani phone number. Use formats like: +923XXXXXXXXX or 03XXXXXXXXX"
        )

    return f"+{normalized}"


def validate_no_past_date(d: date, field_name: str):
    if d < date.today():
        raise ValueError(f"Past dates are not allowed for {field_name}")


def _sync_active_flag(member: Member) -> None:
    today = date.today()
    if member.expiry_date < today:
        member.status = 'Expired'
        member.is_active = False
    elif member.status == 'Active':
        member.is_active = True
    elif member.status == 'Inactive':
        member.is_active = False
    elif member.status == 'Expired':
        member.is_active = False


@strawberry.input
class MemberInput:
    full_name: str
    phone_number: str
    membership_plan_id: UUID
    join_date: typing.Optional[date] = None
    father_name: typing.Optional[str] = None
    cnic: typing.Optional[str] = None
    address: typing.Optional[str] = None
    notes: typing.Optional[str] = None


@strawberry.input
class UpdateMemberInput:
    full_name: typing.Optional[str] = None
    phone_number: typing.Optional[str] = None
    membership_plan_id: typing.Optional[UUID] = None
    father_name: typing.Optional[str] = None
    cnic: typing.Optional[str] = None
    address: typing.Optional[str] = None
    notes: typing.Optional[str] = None
    status: typing.Optional[str] = None
    expiry_date: typing.Optional[date] = None
    join_date: typing.Optional[date] = None


@strawberry.input
class MembershipPlanInput:
    plan_name: str
    price: float
    duration_months: int
    description: typing.Optional[str] = None
    duration_days: typing.Optional[int] = None


@strawberry.input
class GymSettingsInput:
    gym_name: typing.Optional[str] = None
    address: typing.Optional[str] = None
    contact_number: typing.Optional[str] = None
    whatsapp_number: typing.Optional[str] = None
    currency: typing.Optional[str] = None
    tax_percentage: typing.Optional[float] = None
    payment_reminders: typing.Optional[bool] = None
    membership_expiry_alerts: typing.Optional[bool] = None
    dark_mode: typing.Optional[bool] = None


@strawberry.type
class Mutation:
    @strawberry.mutation
    def create_member(self, input: MemberInput) -> MemberType:
        phone = validate_pakistani_phone(input.phone_number)
        plan = MembershipPlan.objects.get(id=input.membership_plan_id)

        join_date = input.join_date or date.today()
        validate_no_past_date(join_date, "Join date")

        expiry_date = calculate_expiry_date(join_date, plan)

        member = Member.objects.create(
            full_name=input.full_name,
            phone_number=phone,
            membership_plan=plan,
            father_name=input.father_name,
            cnic=input.cnic,
            address=input.address,
            notes=input.notes,
            join_date=join_date,
            expiry_date=expiry_date,
            status='Active',
            is_active=True,
        )
        return member_to_type(member)

    @strawberry.mutation
    def update_member(self, member_id: UUID, input: UpdateMemberInput) -> MemberType:
        member = Member.objects.select_related('membership_plan').get(id=member_id)
        if input.full_name is not None:
            member.full_name = input.full_name
        if input.phone_number is not None:
            member.phone_number = validate_pakistani_phone(input.phone_number)
        if input.father_name is not None:
            member.father_name = input.father_name
        if input.cnic is not None:
            member.cnic = input.cnic
        if input.address is not None:
            member.address = input.address
        if input.notes is not None:
            member.notes = input.notes
        if input.join_date is not None:
            validate_no_past_date(input.join_date, "Join date")
            member.join_date = input.join_date
        if input.membership_plan_id is not None:
            plan = MembershipPlan.objects.get(id=input.membership_plan_id)
            member.membership_plan = plan
            base = member.join_date
            member.expiry_date = calculate_expiry_date(base, plan)
        if input.expiry_date is not None:
            member.expiry_date = input.expiry_date
        if input.status is not None:
            if input.status not in ('Active', 'Inactive', 'Expired'):
                raise ValueError('Invalid status. Use Active, Inactive, or Expired.')
            member.status = input.status
            if input.status == 'Active' and member.expiry_date < date.today():
                raise ValueError(
                    'Cannot activate: membership validity has ended. Extend expiry date first.'
                )
        _sync_active_flag(member)
        member.save()

        expire_overdue_members()
        member.refresh_from_db()
        return member_to_type(member)

    @strawberry.mutation
    def delete_member(self, member_id: UUID) -> bool:
        m = Member.all_records.select_related('membership_plan').filter(id=member_id).first()
        if not m or m.is_deleted:
            return True
        snapshot_name = m.full_name
        MembershipActivity.objects.create(
            member=None,
            member_name=snapshot_name,
            activity_type='member_deleted',
            description=f'🗑️ {snapshot_name} was deleted',
        )
        m.phone_number = f"__deleted__{m.id.hex}"[:40]
        m.is_deleted = True
        m.deleted_at = timezone.now()
        m.is_active = False
        m.save(
            update_fields=[
                'phone_number',
                'is_deleted',
                'deleted_at',
                'is_active',
                'updated_at',
            ]
        )
        return True

    @strawberry.mutation
    def create_membership_plan(self, input: MembershipPlanInput) -> MembershipPlanType:
        plan = MembershipPlan.objects.create(
            plan_name=input.plan_name,
            price=input.price,
            duration_months=input.duration_months,
            description=input.description,
            duration_days=input.duration_days,
        )
        return plan_to_type(plan)

    @strawberry.mutation
    def update_membership_plan(
        self, plan_id: UUID, input: MembershipPlanInput
    ) -> MembershipPlanType:
        plan = MembershipPlan.objects.get(id=plan_id)
        plan.plan_name = input.plan_name
        plan.price = input.price
        plan.duration_months = input.duration_months
        plan.description = input.description
        plan.duration_days = input.duration_days
        plan.save()
        return plan_to_type(plan)

    @strawberry.mutation
    def delete_membership_plan(self, plan_id: UUID) -> bool:
        MembershipPlan.objects.filter(id=plan_id).delete()
        return True

    @strawberry.mutation
    def update_gym_settings(self, input: GymSettingsInput) -> GymSettingsType:
        settings, _ = GymSettings.objects.get_or_create(
            id=UUID('00000000-0000-0000-0000-000000000001')
        )
        if input.gym_name is not None:
            settings.gym_name = input.gym_name
        if input.address is not None:
            settings.address = input.address
        if input.contact_number is not None:
            settings.contact_number = input.contact_number
        if input.whatsapp_number is not None:
            settings.whatsapp_number = input.whatsapp_number
        if input.currency is not None:
            settings.currency = input.currency
        if input.tax_percentage is not None:
            settings.tax_percentage = input.tax_percentage
        if input.payment_reminders is not None:
            settings.payment_reminders = input.payment_reminders
        if input.membership_expiry_alerts is not None:
            settings.membership_expiry_alerts = input.membership_expiry_alerts
        if input.dark_mode is not None:
            settings.dark_mode = input.dark_mode
        settings.save()

        return GymSettingsType(
            id=settings.id,
            gym_name=settings.gym_name,
            gym_logo=settings.gym_logo.url if settings.gym_logo else None,
            address=settings.address,
            contact_number=settings.contact_number,
            whatsapp_number=settings.whatsapp_number,
            currency=settings.currency,
            tax_percentage=float(settings.tax_percentage),
            payment_reminders=settings.payment_reminders,
            membership_expiry_alerts=settings.membership_expiry_alerts,
            dark_mode=settings.dark_mode,
        )

    @strawberry.mutation
    def delete_payment(self, payment_id: UUID) -> bool:
        FeeRecord.objects.filter(id=payment_id).delete()
        return True

    @strawberry.mutation
    def create_payment(
        self,
        member_id: UUID,
        amount: float,
        month_str: str,
        renew_membership: bool = False,
    ) -> bool:
        member = Member.objects.select_related('membership_plan').get(id=member_id)
        month_date = date.fromisoformat(month_str)
        today_month = date.today().replace(day=1)
        if month_date.replace(day=1) < today_month:
            raise ValueError('Past months are not allowed for fee payment')

        if member.status == 'Expired':
            if not renew_membership:
                raise ValueError(
                    "This membership has expired. Use 'Renew membership' payment to renew."
                )
            pay_date = date.today()
            plan = member.membership_plan
            FeeRecord.objects.update_or_create(
                member=member,
                month=month_date.replace(day=1),
                defaults={
                    'amount': amount,
                    'payment_date': pay_date,
                    'status': 'Paid',
                },
            )
            member.join_date = pay_date
            member.expiry_date = calculate_expiry_date(pay_date, plan)
            member.status = 'Active'
            member.is_active = True
            member.save(
                update_fields=[
                    'join_date',
                    'expiry_date',
                    'status',
                    'is_active',
                    'updated_at',
                ]
            )
            MembershipActivity.objects.create(
                member=member,
                member_name=member.full_name,
                activity_type='membership_renewed',
                description=(
                    f'💰 {member.full_name} renewed membership '
                    f'for {member.membership_plan.plan_name}'
                ),
            )
            return True


        FeeRecord.objects.update_or_create(
            member=member,
            month=month_date.replace(day=1),
            defaults={
                'amount': amount,
                'payment_date': date.today(),
                'status': 'Paid',
            },
        )
        return True

    @strawberry.mutation
    def renew_membership(
        self,
        member_id: UUID,
        membership_plan_id: typing.Optional[UUID] = None,
    ) -> MemberType:
        """Extend validity without recording a fee (admin override). Prefer create_payment(..., renew_membership=true)."""
        member = Member.objects.select_related('membership_plan').get(id=member_id)
        plan = (
            MembershipPlan.objects.get(id=membership_plan_id)
            if membership_plan_id
            else member.membership_plan
        )
        today = date.today()
        start = member.expiry_date if member.expiry_date >= today else today
        member.membership_plan = plan
        if member.status == 'Expired':
            member.join_date = start
        member.expiry_date = calculate_expiry_date(start, plan)
        member.status = 'Active'
        member.is_active = True
        member.save()
        MembershipActivity.objects.create(
            member=member,
            member_name=member.full_name,
            activity_type='membership_renewed',
            description=(
                f'💰 {member.full_name} renewed membership '
                f'for {member.membership_plan.plan_name} (manual renewal)'
            ),
        )
        return member_to_type(member)
