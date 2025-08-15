from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User
from django.shortcuts import render, redirect
from django.urls import reverse
from django import forms

from .models import UserProfile


class RegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    phone_number = forms.CharField(required=False)
    profile_picture = forms.ImageField(required=False)

    class Meta:
        model = User
        fields = [
            'username',
            'email',
            'first_name',
            'last_name',
            'password1',
            'password2',
        ]


def register_view(request):
    if request.method == 'POST':
        form = RegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save(commit=False)
            user.email = form.cleaned_data['email']
            user.save()
            UserProfile.objects.create(
                user=user,
                phone_number=form.cleaned_data.get('phone_number', ''),
                profile_picture=form.cleaned_data.get('profile_picture'),
                role=UserProfile.ROLE_CUSTOMER,
            )
            messages.success(request, 'Registration successful. Please log in.')
            return redirect('login')
        messages.error(request, 'Please correct the errors below.')
    else:
        form = RegistrationForm()
    return render(request, 'users/register.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('dashboard')
        messages.error(request, 'Invalid credentials')
    else:
        form = AuthenticationForm()
    return render(request, 'users/login.html', {'form': form})


def logout_view(request):
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('login')


class ProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['phone_number', 'profile_picture']


@login_required
def profile_view(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        user = request.user
        user.first_name = request.POST.get('first_name', user.first_name)
        user.last_name = request.POST.get('last_name', user.last_name)
        user.email = request.POST.get('email', user.email)
        user.save()

        form = ProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated.')
            return redirect('profile')
        messages.error(request, 'Please fix the errors below.')
    else:
        form = ProfileForm(instance=profile)
    return render(request, 'users/profile.html', {'form': form})


def _is_bank_admin(user) -> bool:
    try:
        if not user.is_authenticated:
            return False
        if getattr(user, 'is_superuser', False):
            return True
        return getattr(user, 'profile', None) and user.profile.role == UserProfile.ROLE_ADMIN
    except Exception:
        return False


class AdminCreateUserForm(forms.Form):
    username = forms.CharField(max_length=150)
    email = forms.EmailField(required=True)
    first_name = forms.CharField(required=False)
    last_name = forms.CharField(required=False)
    phone_number = forms.CharField(required=False)
    role = forms.ChoiceField(choices=UserProfile.ROLE_CHOICES, initial=UserProfile.ROLE_CUSTOMER)
    password = forms.CharField(widget=forms.PasswordInput)
    confirm_password = forms.CharField(widget=forms.PasswordInput)
    profile_picture = forms.ImageField(required=False)
    initial_deposit = forms.DecimalField(max_digits=12, decimal_places=2, required=False, initial=0)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('password') != cleaned.get('confirm_password'):
            raise forms.ValidationError('Passwords do not match')
        return cleaned


@login_required
def admin_create_user_view(request):
    if not _is_bank_admin(request.user):
        messages.error(request, 'Admins only')
        return redirect('dashboard')
    if request.method == 'POST':
        form = AdminCreateUserForm(request.POST, request.FILES)
        if form.is_valid():
            if User.objects.filter(username=form.cleaned_data['username']).exists():
                form.add_error('username', 'Username already exists')
            else:
                user = User.objects.create(
                    username=form.cleaned_data['username'],
                    email=form.cleaned_data['email'],
                    first_name=form.cleaned_data.get('first_name', ''),
                    last_name=form.cleaned_data.get('last_name', ''),
                )
                user.set_password(form.cleaned_data['password'])
                user.save()
                # Ensure profile exists and update
                profile, _ = UserProfile.objects.get_or_create(user=user)
                profile.phone_number = form.cleaned_data.get('phone_number', '')
                profile.role = form.cleaned_data.get('role')
                pic = form.cleaned_data.get('profile_picture')
                if pic:
                    profile.profile_picture = pic
                profile.save()

                # Initial deposit to first account (create if missing)
                from decimal import Decimal
                from bank.models import Account
                from transactions.models import Transaction
                from transactions.utils import generate_transaction_receipt_pdf
                import uuid
                initial = Decimal(str(form.cleaned_data.get('initial_deposit') or 0))
                if initial > 0:
                    account = Account.objects.filter(user=user).order_by('created_at').first()
                    if account is None:
                        # Fallback: create a default savings
                        from users.signals import generate_account_number
                        number = generate_account_number()
                        while Account.objects.filter(account_number=number).exists():
                            number = generate_account_number()
                        account = Account.objects.create(user=user, account_number=number, account_type=Account.TYPE_SAVINGS, interest_rate=2.5)
                    from django.db import transaction as dbtx
                    with dbtx.atomic():
                        account.balance += initial
                        account.save(update_fields=['balance'])
                        t = Transaction.objects.create(
                            user=user,
                            account=account,
                            transaction_type=Transaction.TYPE_DEPOSIT,
                            category=Transaction.CATEGORY_OTHER,
                            amount=initial,
                            description='Initial deposit (user creation)',
                            nonce=str(uuid.uuid4()),
                        )
                        t.receipt_pdf.save(f'receipt_{t.id}.pdf', generate_transaction_receipt_pdf(t))

                messages.success(request, f"User '{user.username}' created successfully")
                return redirect('admin_create_user')
    else:
        form = AdminCreateUserForm()
    return render(request, 'users/admin_create_user.html', {'form': form})
