from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard_view, name='dashboard'),
    path('loans/', views.loans_view, name='loans'),
    path('loans/request/', views.request_loan_view, name='request_loan'),
    path('manage/loans/', views.admin_loans_view, name='admin_loans'),
    path('manage/loans/<int:loan_id>/<str:action>/', views.update_loan_status_view, name='update_loan_status'),
    path('manage/accounts/create/', views.admin_create_account_view, name='admin_create_account'),
]

