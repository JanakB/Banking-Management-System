from django.core.management.base import BaseCommand
from bank.models import Account


class Command(BaseCommand):
    help = 'Apply monthly interest to all savings accounts'

    def handle(self, *args, **options):
        count = 0
        for account in Account.objects.filter(account_type=Account.TYPE_SAVINGS):
            interest = account.accrue_monthly_interest()
            if interest and interest > 0:
                count += 1
        self.stdout.write(self.style.SUCCESS(f'Applied interest for {count} accounts'))

