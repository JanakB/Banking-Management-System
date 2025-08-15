from django.db import models
from django.contrib.auth.models import User
from bank.models import Account


class Transaction(models.Model):
    TYPE_DEPOSIT = 'deposit'
    TYPE_WITHDRAW = 'withdraw'
    TYPE_TRANSFER = 'transfer'
    TRANSACTION_TYPE_CHOICES = [
        (TYPE_DEPOSIT, 'Deposit'),
        (TYPE_WITHDRAW, 'Withdraw'),
        (TYPE_TRANSFER, 'Transfer'),
    ]

    CATEGORY_SALARY = 'salary'
    CATEGORY_BILLS = 'bills'
    CATEGORY_SHOPPING = 'shopping'
    CATEGORY_OTHER = 'other'
    CATEGORY_CHOICES = [
        (CATEGORY_SALARY, 'Salary'),
        (CATEGORY_BILLS, 'Bills'),
        (CATEGORY_SHOPPING, 'Shopping'),
        (CATEGORY_OTHER, 'Other'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transactions')
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='transactions')
    related_account = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, blank=True, related_name='related_transactions')
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE_CHOICES)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default=CATEGORY_OTHER)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    receipt_pdf = models.FileField(upload_to='receipts/', null=True, blank=True)
    nonce = models.CharField(max_length=64, unique=True, help_text='Idempotency token to prevent duplicate transactions')

    def __str__(self) -> str:
        return f"{self.get_transaction_type_display()} {self.amount} on {self.created_at:%Y-%m-%d}"


class Beneficiary(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='beneficiaries')
    name = models.CharField(max_length=100)
    nickname = models.CharField(max_length=50, blank=True)
    account_number = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.nickname or self.name


class ScheduledTransfer(models.Model):
    FREQ_ONCE = 'once'
    FREQ_DAILY = 'daily'
    FREQ_WEEKLY = 'weekly'
    FREQ_MONTHLY = 'monthly'
    FREQ_CHOICES = [
        (FREQ_ONCE, 'One-time'),
        (FREQ_DAILY, 'Daily'),
        (FREQ_WEEKLY, 'Weekly'),
        (FREQ_MONTHLY, 'Monthly'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='scheduled_transfers')
    from_account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='scheduled_outgoing')
    to_identifier = models.CharField(max_length=255, help_text='Recipient account number or email')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    category = models.CharField(max_length=20, choices=Transaction.CATEGORY_CHOICES, default=Transaction.CATEGORY_OTHER)
    description = models.CharField(max_length=255, blank=True)
    frequency = models.CharField(max_length=20, choices=FREQ_CHOICES, default=FREQ_MONTHLY)
    next_run = models.DateTimeField()
    last_run = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Scheduled {self.amount} {self.frequency}"

# Create your models here.
