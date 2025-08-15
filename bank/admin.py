from django.contrib import admin
from .models import Account, Loan


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ('account_number', 'user', 'account_type', 'balance', 'interest_rate', 'created_at')
    search_fields = ('account_number', 'user__username', 'user__email')
    list_filter = ('account_type',)


@admin.register(Loan)
class LoanAdmin(admin.ModelAdmin):
    list_display = ('user', 'amount', 'status', 'created_at')
    list_filter = ('status',)
