from django.core.management.base import BaseCommand
from django.db import transaction as dbtx
from django.utils import timezone
from transactions.models import ScheduledTransfer, Transaction
from bank.models import Account
from transactions.utils import generate_transaction_receipt_pdf
import uuid


def resolve_recipient(identifier: str):
    if identifier.isdigit():
        return Account.objects.filter(account_number=identifier).first()
    return Account.objects.filter(user__email__iexact=identifier).first()


class Command(BaseCommand):
    help = 'Execute due scheduled transfers'

    def handle(self, *args, **options):
        now = timezone.now()
        due = ScheduledTransfer.objects.filter(is_active=True, next_run__lte=now)
        processed = 0
        for s in due:
            to_account = resolve_recipient(s.to_identifier)
            if to_account is None or s.from_account.balance < s.amount:
                continue
            with dbtx.atomic():
                s.from_account.balance -= s.amount
                to_account.balance += s.amount
                s.from_account.save(update_fields=['balance'])
                to_account.save(update_fields=['balance'])
                t = Transaction.objects.create(
                    user=s.user,
                    account=s.from_account,
                    related_account=to_account,
                    transaction_type=Transaction.TYPE_TRANSFER,
                    category=s.category,
                    amount=s.amount,
                    description=f"Scheduled: {s.description}",
                    nonce=str(uuid.uuid4()),
                )
                t.receipt_pdf.save(f'receipt_{t.id}.pdf', generate_transaction_receipt_pdf(t))
                s.last_run = now
                # compute next run
                if s.frequency == ScheduledTransfer.FREQ_ONCE:
                    s.is_active = False
                elif s.frequency == ScheduledTransfer.FREQ_DAILY:
                    s.next_run = s.next_run + timezone.timedelta(days=1)
                elif s.frequency == ScheduledTransfer.FREQ_WEEKLY:
                    s.next_run = s.next_run + timezone.timedelta(weeks=1)
                else:
                    # monthly: add approx 30 days
                    s.next_run = s.next_run + timezone.timedelta(days=30)
                s.save(update_fields=['last_run', 'is_active', 'next_run'])
            processed += 1
        self.stdout.write(self.style.SUCCESS(f'Processed {processed} scheduled transfers'))

