import uuid
from django.db import models
from apps.members.models import Member

class FeeRecord(models.Model):
    STATUS_CHOICES = (
        ('Paid', 'Paid'),
        ('Unpaid', 'Unpaid'),
        ('Expired', 'Expired'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name='fee_records')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    month = models.DateField(help_text="Month for which the fee is paid/due (e.g. 2025-01-01 for Jan 2025)")
    payment_date = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Unpaid')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.member.full_name} - {self.month} ({self.status})"
