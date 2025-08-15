from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal


class Account(models.Model):
    TYPE_SAVINGS = 'savings'
    TYPE_CURRENT = 'current'
    ACCOUNT_TYPE_CHOICES = [
        (TYPE_SAVINGS, 'Savings'),
        (TYPE_CURRENT, 'Current'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='accounts')
    account_number = models.CharField(max_length=20, unique=True)
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPE_CHOICES, default=TYPE_SAVINGS)
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    last_interest_applied = models.DateField(blank=True, null=True)

    def __str__(self) -> str:
        return f"{self.account_number} ({self.get_account_type_display()})"

    def accrue_monthly_interest(self) -> Decimal:
        if self.account_type != self.TYPE_SAVINGS or self.interest_rate <= 0:
            return Decimal('0.00')

        today = timezone.now().date()
        if self.last_interest_applied and self.last_interest_applied.month == today.month and self.last_interest_applied.year == today.year:
            return Decimal('0.00')

        interest = (self.balance * self.interest_rate) / Decimal('1200')
        self.balance += interest
        self.last_interest_applied = today
        self.save(update_fields=['balance', 'last_interest_applied'])
        return interest


class Loan(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_REJECTED, 'Rejected'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='loans')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    purpose = models.TextField()
    document = models.FileField(upload_to='loan_docs/', null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Loan({self.user.username}, {self.amount}, {self.status})"

# Create your models here.
