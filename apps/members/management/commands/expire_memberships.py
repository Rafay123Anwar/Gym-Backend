"""Daily job: expire memberships past their validity date.

Schedule via Windows Task Scheduler, cron, or:
  python manage.py expire_memberships
"""
from django.core.management.base import BaseCommand

from apps.members.services import expire_overdue_members


class Command(BaseCommand):
    help = 'Expire memberships where today is past expiry_date'

    def handle(self, *args, **options):
        count = expire_overdue_members()
        self.stdout.write(
            self.style.SUCCESS(f'Expired {count} membership(s).')
        )
