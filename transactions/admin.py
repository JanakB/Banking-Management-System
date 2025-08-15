from django.contrib import admin
from .models import Transaction, Beneficiary, ScheduledTransfer


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('user', 'account', 'transaction_type', 'category', 'amount', 'created_at')
    list_filter = ('transaction_type', 'category')
    search_fields = ('account__account_number', 'user__username')


@admin.register(Beneficiary)
class BeneficiaryAdmin(admin.ModelAdmin):
    list_display = ('user', 'name', 'nickname', 'account_number', 'email', 'created_at')
    search_fields = ('name', 'nickname', 'account_number', 'email')


@admin.register(ScheduledTransfer)
class ScheduledTransferAdmin(admin.ModelAdmin):
    list_display = ('user', 'from_account', 'to_identifier', 'amount', 'frequency', 'next_run', 'is_active')
    list_filter = ('frequency', 'is_active')
