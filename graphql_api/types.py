import typing
import strawberry
from django.contrib.auth import get_user_model
from apps.members.models import Member, MembershipPlan
from apps.payments.models import FeeRecord
from datetime import date, datetime
from uuid import UUID

User = get_user_model()

@strawberry.type
class UserType:
    id: UUID
    username: str
    email: str

@strawberry.type
class MembershipPlanType:
    id: UUID
    plan_name: str
    description: typing.Optional[str]
    price: float
    duration_months: int
    duration_days: typing.Optional[int]
    is_active: bool
    created_at: datetime

@strawberry.type
class MemberType:
    id: UUID
    full_name: str
    father_name: typing.Optional[str]
    phone_number: str
    cnic: typing.Optional[str]
    address: typing.Optional[str]
    notes: typing.Optional[str]
    join_date: date
    start_date: date
    expiry_date: date
    status: str
    is_active: bool
    membership_plan: MembershipPlanType
    paid_status: str
    days_until_expiry: typing.Optional[int] = None

@strawberry.type
class FeeRecordType:
    id: UUID
    amount: float
    month: date
    payment_date: typing.Optional[date]
    status: str
    member: MemberType

@strawberry.type
class GymSettingsType:
    id: UUID
    gym_name: str
    gym_logo: typing.Optional[str]
    address: typing.Optional[str]
    contact_number: typing.Optional[str]
    whatsapp_number: typing.Optional[str]
    currency: str
    tax_percentage: float
    payment_reminders: bool
    membership_expiry_alerts: bool
    dark_mode: bool

@strawberry.type
class ChartDataPoint:
    name: str
    value: float

@strawberry.type
class DashboardStatsType:
    total_members: int
    active_members: int
    inactive_members: int
    expired_members: int
    paid_members: int
    unpaid_members: int
    monthly_revenue: float
    annual_revenue: float
    new_members_this_month: int
    revenue_trend: typing.List[ChartDataPoint]
    member_growth: typing.List[ChartDataPoint]


@strawberry.type
class PaginatedMembersType:
    count: int
    next: typing.Optional[str]
    previous: typing.Optional[str]
    page: int
    total_pages: int
    results: typing.List[MemberType]


@strawberry.type
class PaginatedPaymentsType:
    count: int
    next: typing.Optional[str]
    previous: typing.Optional[str]
    page: int
    total_pages: int
    results: typing.List['FeeRecordType']


@strawberry.type
class PaginatedPlansType:
    count: int
    next: typing.Optional[str]
    previous: typing.Optional[str]
    page: int
    total_pages: int
    results: typing.List[MembershipPlanType]


@strawberry.type
class ExpiryAlertType:
    member_id: UUID
    member_name: str
    expiry_date: date
    days_remaining: int
    level: str
    message: str


@strawberry.type
class RecentActivityType:
    id: UUID
    activity_type: str
    description: str
    created_at: datetime
    member_name: typing.Optional[str] = None


@strawberry.type
class PaginatedActivitiesType:
    count: int
    next: typing.Optional[str]
    previous: typing.Optional[str]
    page: int
    total_pages: int
    results: typing.List[RecentActivityType]
