from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.db.models.functions import TruncMonth
import json
from django.http import HttpResponseForbidden, HttpResponseBadRequest
from django.shortcuts import render, redirect, get_object_or_404
from django import forms

from bank.models import Account, Loan
from transactions.models import Transaction
from django.contrib.auth.models import User


@login_required
def dashboard_view(request):
    accounts = Account.objects.filter(user=request.user)
    transactions = Transaction.objects.filter(user=request.user).order_by('-created_at')[:10]

    total_deposits = Transaction.objects.filter(user=request.user, transaction_type=Transaction.TYPE_DEPOSIT).aggregate(Sum('amount'))['amount__sum'] or 0
    total_withdrawals = Transaction.objects.filter(user=request.user, transaction_type=Transaction.TYPE_WITHDRAW).aggregate(Sum('amount'))['amount__sum'] or 0

    loans = Loan.objects.filter(user=request.user).order_by('-created_at')[:5]

    # Analytics: group by month for chart (simple)
    monthly_qs = (
        Transaction.objects.filter(user=request.user)
        .annotate(month=TruncMonth('created_at'))
        .values('month', 'transaction_type')
        .annotate(total=Sum('amount'))
        .order_by('month')
    )
    monthly = [
        {
            'month': (row['month'].strftime('%Y-%m') if row['month'] else ''),
            'transaction_type': row['transaction_type'],
            'total': float(row['total'] or 0),
        }
        for row in monthly_qs
    ]
    monthly_json = json.dumps(monthly)

    return render(
        request,
        'bank/dashboard.html',
        {
            'accounts': accounts,
            'transactions': transactions,
            'total_deposits': total_deposits,
            'total_withdrawals': total_withdrawals,
            'loans': loans,
            'monthly_json': monthly_json,
        },
    )


class LoanRequestForm(forms.Form):
    amount = forms.DecimalField(max_digits=12, decimal_places=2, min_value=0.01)
    purpose = forms.CharField(widget=forms.Textarea(attrs={'rows': 4}))
    document = forms.FileField(required=False)


@login_required
def request_loan_view(request):
    if request.method == 'POST':
        form = LoanRequestForm(request.POST, request.FILES)
        if form.is_valid():
            Loan.objects.create(
                user=request.user,
                amount=form.cleaned_data['amount'],
                purpose=form.cleaned_data['purpose'],
                document=form.cleaned_data.get('document'),
            )
            from django.contrib import messages
            messages.success(request, 'Loan request submitted.')
            return redirect('loans')
    else:
        form = LoanRequestForm()
    return render(request, 'bank/loan_request.html', {'form': form})


@login_required
def loans_view(request):
    loans = Loan.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'bank/loans.html', {'loans': loans})


def _is_bank_admin(user) -> bool:
    try:
        if not user.is_authenticated:
            return False
        if getattr(user, 'is_superuser', False):
            return True
        return getattr(user, 'profile', None) and user.profile.role == 'admin'
    except Exception:
        return False


@login_required
def admin_loans_view(request):
    if not _is_bank_admin(request.user):
        return HttpResponseForbidden('Admins only')
    loans = Loan.objects.all().order_by('-created_at')
    return render(request, 'bank/admin_loans.html', {'loans': loans})


@login_required
def update_loan_status_view(request, loan_id: int, action: str):
    if request.method != 'POST':
        return HttpResponseBadRequest('POST required')
    if not _is_bank_admin(request.user):
        return HttpResponseForbidden('Admins only')
    loan = get_object_or_404(Loan, id=loan_id)
    if action not in ('approve', 'reject'):
        return HttpResponseBadRequest('Invalid action')
    loan.status = Loan.STATUS_APPROVED if action == 'approve' else Loan.STATUS_REJECTED
    loan.save(update_fields=['status'])
    from django.contrib import messages
    messages.success(request, f'Loan {action}d.')
    return redirect('admin_loans')


def _generate_account_number() -> str:
    import random
    return ''.join([str(random.randint(0, 9)) for _ in range(12)])


class AdminCreateAccountForm(forms.Form):
    user = forms.ModelChoiceField(queryset=User.objects.all())
    account_type = forms.ChoiceField(choices=Account.ACCOUNT_TYPE_CHOICES)
    interest_rate = forms.DecimalField(max_digits=5, decimal_places=2, required=False, help_text='Defaults by type if left blank')
    initial_deposit = forms.DecimalField(max_digits=12, decimal_places=2, min_value=0, initial=0)


@login_required
def admin_create_account_view(request):
    if not _is_bank_admin(request.user):
        return HttpResponseForbidden('Admins only')
    if request.method == 'POST':
        form = AdminCreateAccountForm(request.POST)
        if form.is_valid():
            user = form.cleaned_data['user']
            account_type = form.cleaned_data['account_type']
            rate = form.cleaned_data.get('interest_rate')
            if rate is None or rate == '':
                rate = 2.5 if account_type == Account.TYPE_SAVINGS else 0
            # unique account number
            number = _generate_account_number()
            while Account.objects.filter(account_number=number).exists():
                number = _generate_account_number()
            account = Account.objects.create(
                user=user,
                account_number=number,
                account_type=account_type,
                interest_rate=rate,
            )
            # initial deposit
            from decimal import Decimal
            initial = Decimal(str(form.cleaned_data['initial_deposit']))
            if initial > 0:
                from transactions.utils import generate_transaction_receipt_pdf
                from django.db import transaction as dbtx
                import uuid
                with dbtx.atomic():
                    account.balance += initial
                    account.save(update_fields=['balance'])
                    t = Transaction.objects.create(
                        user=user,
                        account=account,
                        transaction_type=Transaction.TYPE_DEPOSIT,
                        category=Transaction.CATEGORY_OTHER,
                        amount=initial,
                        description='Initial deposit (admin)',
                        nonce=str(uuid.uuid4()),
                    )
                    t.receipt_pdf.save(f'receipt_{t.id}.pdf', generate_transaction_receipt_pdf(t))
            from django.contrib import messages
            messages.success(request, f'Account {account.account_number} created for {user.username}.')
            return redirect('dashboard')
    else:
        form = AdminCreateAccountForm()
    return render(request, 'bank/admin_create_account.html', {'form': form})
