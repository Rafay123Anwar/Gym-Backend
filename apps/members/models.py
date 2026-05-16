import uuid
from django.db import models
from django.utils import timezone


class ActiveMemberManager(models.Manager):
    """Excludes soft-deleted members from all default queries."""

    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class MembershipPlan(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    plan_name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    duration_months = models.IntegerField(help_text="Duration in months", default=1)
    duration_days = models.IntegerField(help_text="Duration in days (optional)", blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.plan_name} - Rs. {self.price}"


class Member(models.Model):
    STATUS_CHOICES = (
        ('Active', 'Active'),
        ('Inactive', 'Inactive'),
        ('Expired', 'Expired'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    full_name = models.CharField(max_length=200)
    father_name = models.CharField(max_length=200, blank=True, null=True)
    phone_number = models.CharField(max_length=40, unique=True)
    cnic = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

    membership_plan = models.ForeignKey(MembershipPlan, on_delete=models.PROTECT, related_name='members')
    join_date = models.DateField(help_text='Membership start date')
    expiry_date = models.DateField(help_text='Auto-calculated from plan duration')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Active')
    is_active = models.BooleanField(
        default=True,
        help_text='False when membership expired or manually deactivated',
    )
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ActiveMemberManager()
    all_records = models.Manager()

    class Meta:
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['is_active']),
            models.Index(fields=['expiry_date']),
            models.Index(fields=['phone_number']),
            models.Index(fields=['is_deleted']),
        ]

    def __str__(self):
        return self.full_name

    @property
    def start_date(self):
        """Alias for join_date (membership validity start)."""
        return self.join_date


class MembershipActivity(models.Model):
    """Audit trail for renewals and deletions (shown in Recent Activity)."""

    ACTIVITY_CHOICES = (
        ('membership_renewed', 'Membership renewed'),
        ('member_deleted', 'Member deleted'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    member = models.ForeignKey(
        Member,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='activities',
    )
    member_name = models.CharField(max_length=200)
    activity_type = models.CharField(max_length=40, choices=ACTIVITY_CHOICES)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['-created_at'])]
