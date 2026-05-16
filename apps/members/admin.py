from django.contrib import admin
from .models import Member, MembershipPlan

@admin.register(MembershipPlan)
class MembershipPlanAdmin(admin.ModelAdmin):
    list_display = ('plan_name', 'price', 'duration_days')
    search_fields = ('plan_name',)

@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'phone_number', 'membership_plan', 'join_date', 'expiry_date', 'status')
    list_filter = ('status', 'membership_plan')
    search_fields = ('full_name', 'phone_number', 'cnic')
