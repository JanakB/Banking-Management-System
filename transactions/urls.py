from django.urls import path
from . import views

urlpatterns = [
    path('deposit/', views.deposit_view, name='deposit'),
    path('withdraw/', views.withdraw_view, name='withdraw'),
    path('transfer/', views.transfer_view, name='transfer'),
    path('history/', views.history_view, name='history'),
    path('beneficiaries/', views.beneficiaries_view, name='beneficiaries'),
    path('beneficiaries/add/', views.add_beneficiary_view, name='add_beneficiary'),
    path('beneficiaries/<int:pk>/delete/', views.delete_beneficiary_view, name='delete_beneficiary'),
    path('scheduled/', views.scheduled_transfers_view, name='scheduled_transfers'),
    path('scheduled/add/', views.add_scheduled_transfer_view, name='add_scheduled_transfer'),
]

