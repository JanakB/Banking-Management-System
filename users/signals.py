from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import UserProfile
from bank.models import Account
import random


def generate_account_number() -> str:
    return ''.join([str(random.randint(0, 9)) for _ in range(12)])


@receiver(post_save, sender=User)
def create_profile_and_account(sender, instance: User, created: bool, **kwargs):
    if created:
        UserProfile.objects.get_or_create(user=instance)
        from bank.models import Account
        account_number = generate_account_number()
        # Ensure unique account number
        while Account.objects.filter(account_number=account_number).exists():
            account_number = generate_account_number()
        Account.objects.create(
            user=instance,
            account_number=account_number,
            account_type=Account.TYPE_SAVINGS,
            interest_rate=2.5,
        )

