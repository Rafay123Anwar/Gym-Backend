from django.db import models
import uuid

class GymSettings(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    gym_name = models.CharField(max_length=255, default="IRON CORE")
    gym_logo = models.ImageField(upload_to='gym_logos/', blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    contact_number = models.CharField(max_length=20, blank=True, null=True)
    whatsapp_number = models.CharField(max_length=20, blank=True, null=True)
    currency = models.CharField(max_length=10, default="Rs.")
    tax_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    
    # Notifications
    payment_reminders = models.BooleanField(default=True)
    membership_expiry_alerts = models.BooleanField(default=True)
    
    # System
    dark_mode = models.BooleanField(default=True)
    
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.gym_name

    class Meta:
        verbose_name = "Gym Settings"
        verbose_name_plural = "Gym Settings"
