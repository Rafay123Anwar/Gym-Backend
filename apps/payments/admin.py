from django.contrib import admin
from .models import FeeRecord

@admin.register(FeeRecord)
class FeeRecordAdmin(admin.ModelAdmin):
    list_display = ('member', 'amount', 'month', 'payment_date', 'status')
    list_filter = ('status', 'month')
    search_fields = ('member__full_name',)
