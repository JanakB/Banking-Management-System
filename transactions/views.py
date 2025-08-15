from decimal import Decimal
import uuid

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction as db_transaction
from django.shortcuts import render, redirect, get_object_or_404
from django import forms

from bank.models import Account
from .models import Transaction, Beneficiary, ScheduledTransfer
from .utils import generate_transaction_receipt_pdf


class DepositForm(forms.Form):
    account = forms.ModelChoiceField(queryset=Account.objects.none())
    amount = forms.DecimalField(min_value=Decimal('0.01'), decimal_places=2, max_digits=12)
    category = forms.ChoiceField(choices=Transaction.CATEGORY_CHOICES)
    description = forms.CharField(required=False)

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user')
        super().__init__(*args, **kwargs)
        self.fields['account'].queryset = Account.objects.filter(user=user)


class WithdrawForm(DepositForm):
    pass


class TransferForm(forms.Form):
    from_account = forms.ModelChoiceField(queryset=Account.objects.none())
    beneficiary = forms.ModelChoiceField(queryset=Beneficiary.objects.none(), required=False)
    to_identifier = forms.CharField(help_text='Recipient account number or email')
    amount = forms.DecimalField(min_value=Decimal('0.01'), decimal_places=2, max_digits=12)
    category = forms.ChoiceField(choices=Transaction.CATEGORY_CHOICES)
    description = forms.CharField(required=False)

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user')
        super().__init__(*args, **kwargs)
        self.fields['from_account'].queryset = Account.objects.filter(user=user)
        self.fields['beneficiary'].queryset = Beneficiary.objects.filter(user=user)


class TransactionFilterForm(forms.Form):
    transaction_type = forms.ChoiceField(choices=[('', 'All')] + list(Transaction.TRANSACTION_TYPE_CHOICES), required=False)
    category = forms.ChoiceField(choices=[('', 'All')] + list(Transaction.CATEGORY_CHOICES), required=False)
    start_date = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    end_date = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    account = forms.ModelChoiceField(queryset=Account.objects.none(), required=False)

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user')
        super().__init__(*args, **kwargs)
        self.fields['account'].queryset = Account.objects.filter(user=user)


@login_required
def deposit_view(request):
    if request.method == 'POST':
        form = DepositForm(request.POST, user=request.user)
        if form.is_valid():
            account = form.cleaned_data['account']
            amount = form.cleaned_data['amount']
            with db_transaction.atomic():
                account.balance += amount
                account.save(update_fields=['balance'])
                t = Transaction.objects.create(
                    user=request.user,
                    account=account,
                    transaction_type=Transaction.TYPE_DEPOSIT,
                    category=form.cleaned_data['category'],
                    amount=amount,
                    description=form.cleaned_data.get('description', ''),
                    nonce=str(uuid.uuid4()),
                )
                t.receipt_pdf.save(f"receipt_{t.id}.pdf", generate_transaction_receipt_pdf(t))
            messages.success(request, 'Deposit successful.')
            return redirect('dashboard')
        messages.error(request, 'Please fix the form errors.')
    else:
        form = DepositForm(user=request.user)
    return render(request, 'transactions/deposit.html', {'form': form})


@login_required
def withdraw_view(request):
    if request.method == 'POST':
        form = WithdrawForm(request.POST, user=request.user)
        if form.is_valid():
            account = form.cleaned_data['account']
            amount = form.cleaned_data['amount']
            if account.balance < amount:
                messages.error(request, 'Insufficient balance.')
            else:
                with db_transaction.atomic():
                    account.balance -= amount
                    account.save(update_fields=['balance'])
                    t = Transaction.objects.create(
                        user=request.user,
                        account=account,
                        transaction_type=Transaction.TYPE_WITHDRAW,
                        category=form.cleaned_data['category'],
                        amount=amount,
                        description=form.cleaned_data.get('description', ''),
                        nonce=str(uuid.uuid4()),
                    )
                    t.receipt_pdf.save(f"receipt_{t.id}.pdf", generate_transaction_receipt_pdf(t))
                messages.success(request, 'Withdrawal successful.')
                return redirect('dashboard')
        else:
            messages.error(request, 'Please fix the form errors.')
    else:
        form = WithdrawForm(user=request.user)
    return render(request, 'transactions/withdraw.html', {'form': form})


@login_required
def transfer_view(request):
    if request.method == 'POST':
        form = TransferForm(request.POST, user=request.user)
        if form.is_valid():
            from_account = form.cleaned_data['from_account']
            to_identifier = form.cleaned_data['to_identifier'].strip()
            beneficiary = form.cleaned_data.get('beneficiary')
            if beneficiary and beneficiary.account_number:
                to_identifier = beneficiary.account_number
            elif beneficiary and beneficiary.email:
                to_identifier = beneficiary.email
            amount = form.cleaned_data['amount']

            # Resolve recipient account by account number or email
            to_account = None
            if to_identifier.isdigit():
                to_account = Account.objects.filter(account_number=to_identifier).first()
            else:
                to_account = Account.objects.filter(user__email__iexact=to_identifier).first()

            if to_account is None:
                messages.error(request, 'Recipient not found.')
            elif from_account == to_account:
                messages.error(request, 'Cannot transfer to the same account.')
            elif from_account.balance < amount:
                messages.error(request, 'Insufficient balance.')
            else:
                with db_transaction.atomic():
                    from_account.balance -= amount
                    to_account.balance += amount
                    from_account.save(update_fields=['balance'])
                    to_account.save(update_fields=['balance'])
                    nonce = str(uuid.uuid4())
                    t = Transaction.objects.create(
                        user=request.user,
                        account=from_account,
                        related_account=to_account,
                        transaction_type=Transaction.TYPE_TRANSFER,
                        category=form.cleaned_data['category'],
                        amount=amount,
                        description=form.cleaned_data.get('description', ''),
                        nonce=nonce,
                    )
                    t.receipt_pdf.save(f"receipt_{t.id}.pdf", generate_transaction_receipt_pdf(t))
                messages.success(request, 'Transfer successful.')
                return redirect('dashboard')
        else:
            messages.error(request, 'Please fix the form errors.')
    else:
        form = TransferForm(user=request.user)
    return render(request, 'transactions/transfer.html', {'form': form})


class BeneficiaryForm(forms.ModelForm):
    class Meta:
        model = Beneficiary
        fields = ['name', 'nickname', 'account_number', 'email']


@login_required
def beneficiaries_view(request):
    items = Beneficiary.objects.filter(user=request.user).order_by('name')
    return render(request, 'transactions/beneficiaries.html', {'items': items})


@login_required
def add_beneficiary_view(request):
    if request.method == 'POST':
        form = BeneficiaryForm(request.POST)
        if form.is_valid():
            b = form.save(commit=False)
            b.user = request.user
            b.save()
            messages.success(request, 'Beneficiary added.')
            return redirect('beneficiaries')
    else:
        form = BeneficiaryForm()
    return render(request, 'transactions/add_beneficiary.html', {'form': form})


@login_required
def delete_beneficiary_view(request, pk: int):
    b = get_object_or_404(Beneficiary, pk=pk, user=request.user)
    if request.method == 'POST':
        b.delete()
        messages.info(request, 'Beneficiary removed.')
        return redirect('beneficiaries')
    return render(request, 'transactions/delete_beneficiary.html', {'b': b})


class ScheduledTransferForm(forms.ModelForm):
    class Meta:
        model = ScheduledTransfer
        fields = ['from_account', 'to_identifier', 'amount', 'category', 'description', 'frequency', 'next_run', 'is_active']
        widgets = {
            'next_run': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user')
        super().__init__(*args, **kwargs)
        self.fields['from_account'].queryset = Account.objects.filter(user=user)


@login_required
def scheduled_transfers_view(request):
    items = ScheduledTransfer.objects.filter(user=request.user).order_by('next_run')
    return render(request, 'transactions/scheduled.html', {'items': items})


@login_required
def add_scheduled_transfer_view(request):
    if request.method == 'POST':
        form = ScheduledTransferForm(request.POST, user=request.user)
        if form.is_valid():
            st = form.save(commit=False)
            st.user = request.user
            st.save()
            messages.success(request, 'Scheduled transfer created.')
            return redirect('scheduled_transfers')
    else:
        form = ScheduledTransferForm(user=request.user)
    return render(request, 'transactions/add_scheduled.html', {'form': form})


@login_required
def history_view(request):
    form = TransactionFilterForm(request.GET or None, user=request.user)
    qs = Transaction.objects.filter(user=request.user).select_related('account', 'related_account').order_by('-created_at')
    if form.is_valid():
        ttype = form.cleaned_data.get('transaction_type')
        if ttype:
            qs = qs.filter(transaction_type=ttype)
        cat = form.cleaned_data.get('category')
        if cat:
            qs = qs.filter(category=cat)
        start = form.cleaned_data.get('start_date')
        if start:
            qs = qs.filter(created_at__date__gte=start)
        end = form.cleaned_data.get('end_date')
        if end:
            qs = qs.filter(created_at__date__lte=end)
        account = form.cleaned_data.get('account')
        if account:
            qs = qs.filter(account=account)
    export = request.GET.get('export')
    if export == 'csv':
        import csv
        from django.http import HttpResponse
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="transactions.csv"'
        writer = csv.writer(response)
        writer.writerow(['Date', 'Type', 'Category', 'Account', 'Related', 'Amount', 'Description'])
        for t in qs:
            writer.writerow([t.created_at.strftime('%Y-%m-%d %H:%M'), t.get_transaction_type_display(), t.get_category_display(), t.account.account_number, t.related_account.account_number if t.related_account else '', str(t.amount), t.description])
        return response
    if export == 'pdf':
        from io import BytesIO
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
        from django.http import HttpResponse
        buffer = BytesIO()
        pdf = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter
        y = height - 72
        pdf.setFont('Helvetica-Bold', 16)
        pdf.drawString(72, y, 'BankX Statement')
        y -= 24
        pdf.setFont('Helvetica', 10)
        for t in qs[:1000]:
            line = f"{t.created_at:%Y-%m-%d %H:%M}  {t.get_transaction_type_display()}  ${t.amount}  {t.account.account_number}  {t.get_category_display()}  {t.description}"
            pdf.drawString(72, y, line[:110])
            y -= 14
            if y < 72:
                pdf.showPage()
                y = height - 72
                pdf.setFont('Helvetica', 10)
        pdf.showPage()
        pdf.save()
        buffer.seek(0)
        response = HttpResponse(buffer.read(), content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="statement.pdf"'
        return response

    return render(request, 'transactions/history.html', {'form': form, 'transactions': qs})
