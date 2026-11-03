import strawberry  # type: ignore[import]
import typing
from django.db.models import Sum, Q ,Value
from django.db.models.functions import Concat
from .types import (
    MemberType,
    FeeRecordType,
    DashboardStatsType,
    MembershipPlanType,
    GymSettingsType,
    ChartDataPoint,
    PaginatedMembersType,
    PaginatedPaymentsType,
    PaginatedPlansType,
    ExpiryAlertType,
    PaginatedActivitiesType,
    RecentActivityType,
)
from .helpers import member_to_type, plan_to_type, fee_to_type
from .pagination import paginate_queryset
from apps.members.models import Member, MembershipPlan, MembershipActivity
from apps.members.services import expire_overdue_members, get_expiry_alerts
from apps.payments.models import FeeRecord
from apps.dashboard.models import GymSettings
from datetime import date, timedelta, datetime
from uuid import UUID
import calendar


def _paid_ids_for_month(month_start: date) -> set:
    return set(
        FeeRecord.objects.filter(month=month_start, status='Paid').values_list(
            'member_id', flat=True
        )
    )


def _apply_member_filters(qs, search, status, plan_id, paid_status, active_only=False):

    if search:

        def normalize_pak_phone(value: str) -> str:
            value = (
                value.strip()
                .replace("+", "")
                .replace(" ", "")
                .replace("-", "")
            )

            # 0341 -> 92341
            if value.startswith("0"):
                value = "92" + value[1:]

            return value

        clean = search.strip()

        raw_clean = (
            clean.replace(" ", "")
            .replace("-", "")
            .replace("+", "")
        )

        normalized_phone = normalize_pak_phone(raw_clean)

        qs = qs.annotate(
            full_search=Concat(
                "full_name",
                Value(" "),
                "father_name",
            )
        ).filter(
            Q(full_search__icontains=clean)
            | Q(full_name__icontains=clean)
            | Q(father_name__icontains=clean)
            | Q(phone_number__icontains=raw_clean)
            | Q(phone_number__icontains=normalized_phone)
        )
    
    if status:
        qs = qs.filter(status=status)
    if plan_id:
        qs = qs.filter(membership_plan_id=plan_id)
    if active_only:
        qs = qs.filter(status='Active', is_active=True)
    if paid_status:
        current_month = date.today().replace(day=1)
        paid_ids = _paid_ids_for_month(current_month)
        if paid_status == 'Paid':
            qs = qs.filter(id__in=paid_ids)
        elif paid_status == 'Unpaid':
            qs = qs.exclude(id__in=paid_ids)
        elif paid_status == 'Expired':
            qs = qs.filter(status='Expired')
    return qs


@strawberry.type
class Query:
    @strawberry.field
    def all_members(
        self,
        search: typing.Optional[str] = None,
        status: typing.Optional[str] = None,
        plan_id: typing.Optional[UUID] = None,
        paid_status: typing.Optional[str] = None,
        page: int = 1,
        page_size: int = 10,
        active_only: bool = False,
    ) -> PaginatedMembersType:
        expire_overdue_members()
        qs = Member.objects.select_related('membership_plan').order_by('-created_at')
        qs = _apply_member_filters(qs, search, status, plan_id, paid_status, active_only)
        paged = paginate_queryset(qs, page, page_size)
        paid_ids = _paid_ids_for_month(date.today().replace(day=1))
        results = [member_to_type(m, paid_ids) for m in paged['results']]
        return PaginatedMembersType(
            count=paged['count'],
            next=paged['next'],
            previous=paged['previous'],
            page=paged['page'],
            total_pages=paged['total_pages'],
            results=results,
        )

    @strawberry.field
    def dashboard_stats(self, year: typing.Optional[int] = None) -> DashboardStatsType:
        expire_overdue_members()
        if not year:
            year = date.today().year

        total_members = Member.objects.count()
        active_members = Member.objects.filter(status='Active', is_active=True).count()
        inactive_members = Member.objects.filter(status='Inactive').count()
        expired_members = Member.objects.filter(status='Expired').count()

        current_date = date.today()
        current_month_start = current_date.replace(day=1)

        paid_records = FeeRecord.objects.filter(
            month=current_month_start,
            status='Paid',
            member__is_deleted=False,
        )
        paid_members = paid_records.values('member_id').distinct().count()
        paid_ids = _paid_ids_for_month(current_month_start)
        unpaid_members = Member.objects.filter(status='Active', is_active=True).exclude(id__in=paid_ids).count()

        monthly_revenue = paid_records.aggregate(total=Sum('amount'))['total'] or 0.0
        annual_revenue = (
            FeeRecord.objects.filter(month__year=year, status='Paid').aggregate(
                total=Sum('amount')
            )['total']
            or 0.0
        )

        new_members_this_month = Member.objects.filter(
            join_date__month=current_date.month,
            join_date__year=current_date.year,
        ).count()

        revenue_trend = []
        for i in range(5, -1, -1):
            month_date = (current_month_start - timedelta(days=i * 30)).replace(day=1)
            rev = (
                FeeRecord.objects.filter(month=month_date, status='Paid').aggregate(
                    total=Sum('amount')
                )['total']
                or 0.0
            )
            revenue_trend.append(
                ChartDataPoint(name=month_date.strftime('%b'), value=float(rev))
            )

        member_growth = []
        for i in range(5, -1, -1):
            month_date = (current_month_start - timedelta(days=i * 30)).replace(day=1)
            count = Member.objects.filter(
                join_date__lte=month_date + timedelta(days=31)
            ).count()
            member_growth.append(
                ChartDataPoint(name=month_date.strftime('%b'), value=float(count))
            )

        return DashboardStatsType(
            total_members=total_members,
            active_members=active_members,
            inactive_members=inactive_members,
            expired_members=expired_members,
            paid_members=paid_members,
            unpaid_members=unpaid_members,
            monthly_revenue=float(monthly_revenue),
            annual_revenue=float(annual_revenue),
            new_members_this_month=new_members_this_month,
            revenue_trend=revenue_trend,
            member_growth=member_growth,
        )

    @strawberry.field
    def report_trend(
        self,
        period: str = "monthly",
        year: typing.Optional[int] = None,
        month: typing.Optional[int] = None,
    ) -> typing.List[ChartDataPoint]:
        if not year:
            year = date.today().year

        current_date = date.today()
        current_month_start = current_date.replace(day=1)

        def monthly_trend(selected_year: int) -> typing.List[ChartDataPoint]:
            result: typing.List[ChartDataPoint] = []
            for m in range(1, 13):
                month_start = date(selected_year, m, 1)
                rev = (
                    FeeRecord.objects.filter(month=month_start, status='Paid')
                    .aggregate(total=Sum('amount'))['total']
                    or 0.0
                )
                result.append(
                    ChartDataPoint(
                        name=month_start.strftime('%b'),
                        value=float(rev),
                    )
                )
            return result

        def daily_trend(selected_year: int, selected_month: int) -> typing.List[ChartDataPoint]:
            result: typing.List[ChartDataPoint] = []
            days_in_month = calendar.monthrange(selected_year, selected_month)[1]
            for d in range(1, days_in_month + 1):
                day_date = date(selected_year, selected_month, d)
                rev = (
                    FeeRecord.objects.filter(
                        payment_date=day_date,
                        status='Paid',
                    )
                    .aggregate(total=Sum('amount'))['total']
                    or 0.0
                )
                result.append(
                    ChartDataPoint(
                        name=str(d),
                        value=float(rev),
                    )
                )
            return result

        def yearly_trend(selected_year: int) -> typing.List[ChartDataPoint]:
            result: typing.List[ChartDataPoint] = []
            for y in range(selected_year - 4, selected_year + 1):
                rev = (
                    FeeRecord.objects.filter(month__year=y, status='Paid')
                    .aggregate(total=Sum('amount'))['total']
                    or 0.0
                )
                result.append(
                    ChartDataPoint(
                        name=str(y),
                        value=float(rev),
                    )
                )
            return result

        normalized_period = period.lower()
        if normalized_period == 'daily':
            selected_month = month or current_date.month
            return daily_trend(year, selected_month)
        if normalized_period == 'yearly':
            return yearly_trend(year)
        return monthly_trend(year)

    @strawberry.field
    def all_plans(
        self,
        page: int = 1,
        page_size: int = 50,
    ) -> PaginatedPlansType:
        qs = MembershipPlan.objects.order_by('-created_at')
        paged = paginate_queryset(qs, page, page_size)
        results = [plan_to_type(p) for p in paged['results']]
        return PaginatedPlansType(
            count=paged['count'],
            next=paged['next'],
            previous=paged['previous'],
            page=paged['page'],
            total_pages=paged['total_pages'],
            results=results,
        )

    @strawberry.field
    def gym_settings(self) -> GymSettingsType:
        settings, _ = GymSettings.objects.get_or_create(
            id=UUID('00000000-0000-0000-0000-000000000001')
        )
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

    @strawberry.field
    def member(self, id: UUID) -> typing.Optional[MemberType]:
        expire_overdue_members()
        try:
            m = Member.objects.select_related('membership_plan').get(id=id)
            paid_ids = _paid_ids_for_month(date.today().replace(day=1))
            return member_to_type(m, paid_ids)
        except Member.DoesNotExist:
            return None

    @strawberry.field
    def recent_payments(
        self,
        search: typing.Optional[str] = None,
        month: typing.Optional[str] = None,
        status: typing.Optional[str] = None,
        page: int = 1,
        page_size: int = 10,
        member_status: typing.Optional[str] = None,
        member_id: typing.Optional[UUID] = None,
    ) -> PaginatedPaymentsType:
        expire_overdue_members()
        qs = (
            FeeRecord.objects.select_related('member', 'member__membership_plan')
            .filter(member__is_deleted=False)
            .exclude(member__status='Expired')  
            .order_by('-created_at')
        )

        if search:

            def normalize_pak_phone(value: str) -> str:
                value = (
                    value.strip()
                    .replace("+", "")
                    .replace(" ", "")
                    .replace("-", "")
                )

                # 0341 -> 92341
                if value.startswith("0"):
                    value = "92" + value[1:]

                return value

            clean = search.strip()

            raw_clean = (
                clean.replace(" ", "")
                .replace("-", "")
                .replace("+", "")
            )

            normalized_phone = normalize_pak_phone(raw_clean)

            qs = qs.annotate(
                full_search=Concat(
                    "member__full_name",
                    Value(" "),
                    "member__father_name",
                )
            ).filter(
                Q(full_search__icontains=clean)
                | Q(member__full_name__icontains=clean)
                | Q(member__father_name__icontains=clean)
                | Q(member__phone_number__icontains=raw_clean)
                | Q(member__phone_number__icontains=normalized_phone)
            )
            
            
        if month:
            try:
                qs = qs.filter(month=month)
            except Exception:
                pass

        # if status:
        #     qs = qs.filter(status=status)

        if member_status:
            qs = qs.filter(member__status=member_status)

        if member_id:
            qs = qs.filter(member_id=member_id)

        paged = paginate_queryset(qs, page, page_size)
        paid_ids = _paid_ids_for_month(date.today().replace(day=1))
        results = [fee_to_type(r, paid_ids) for r in paged['results']]
        return PaginatedPaymentsType(
            count=paged['count'],
            next=paged['next'],
            previous=paged['previous'],
            page=paged['page'],
            total_pages=paged['total_pages'],
            results=results,
        )

    @strawberry.field
    def membership_expiry_alerts(
        self, within_days: int = 7
    ) -> typing.List[ExpiryAlertType]:
        expire_overdue_members()
        settings, _ = GymSettings.objects.get_or_create(
            id=UUID('00000000-0000-0000-0000-000000000001')
        )
        if not settings.membership_expiry_alerts:
            return []
        return [
            ExpiryAlertType(
                member_id=a['member_id'],
                member_name=a['member_name'],
                expiry_date=a['expiry_date'],
                days_remaining=a['days_remaining'],
                level=a['level'],
                message=a['message'],
            )
            for a in get_expiry_alerts(within_days)
        ]

    @strawberry.field
    def recent_activities(
        self,
        page: int = 1,
        page_size: int = 10,
    ) -> PaginatedActivitiesType:
        """Activity feed: logged events plus recent joins and payments."""
        expire_overdue_members()
        activities: list[RecentActivityType] = []

        for act in MembershipActivity.objects.all()[:80]:
            activities.append(
                RecentActivityType(
                    id=act.id,
                    activity_type=act.activity_type,
                    description=act.description,
                    created_at=act.created_at,
                    member_name=act.member_name,
                )
            )

        for m in Member.objects.order_by('-created_at')[:50]:
            activities.append(
                RecentActivityType(
                    id=m.id,
                    activity_type='member_joined',
                    description=f'{m.full_name} joined the gym',
                    created_at=m.created_at,
                    member_name=m.full_name,
                )
            )

        for p in (
            FeeRecord.objects.select_related('member')
            .filter(member__is_deleted=False)
            .order_by('-created_at')[:50]
        ):
            activities.append(
                RecentActivityType(
                    id=p.id,
                    activity_type='payment_recorded',
                    description=f'Payment of Rs.{p.amount} from {p.member.full_name}',
                    created_at=p.created_at,
                    member_name=p.member.full_name,
                )
            )

        activities.sort(key=lambda x: x.created_at, reverse=True)
        count = len(activities)
        page = max(1, page)
        page_size = max(1, min(page_size, 50))
        import math

        total_pages = max(1, math.ceil(count / page_size)) if count else 1
        start = (page - 1) * page_size
        end = start + page_size
        page_results = activities[start:end]

        return PaginatedActivitiesType(
            count=count,
            next=str(page + 1) if page < total_pages else None,
            previous=str(page - 1) if page > 1 else None,
            page=page,
            total_pages=total_pages,
            results=page_results,
        )

    @strawberry.field
    def plan(self, id: UUID) -> typing.Optional[MembershipPlanType]:
        try:
            p = MembershipPlan.objects.get(id=id)
            return plan_to_type(p)
        except MembershipPlan.DoesNotExist:
            return None
    
    @strawberry.field
    def member_payment_history(
        self,
        member_id: UUID
    ) -> typing.List[FeeRecordType]:

        records = (
            FeeRecord.objects
            .filter(member_id=member_id)
            .select_related(
                'member',
                'member__membership_plan'
            )
            .order_by('-payment_date')
        )

        paid_ids = _paid_ids_for_month(
            date.today().replace(day=1)
        )

        return [
            fee_to_type(r, paid_ids)
            for r in records
        ]
    


