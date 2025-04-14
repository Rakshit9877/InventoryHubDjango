from django.urls import path
from . import views

app_name = 'admin_dashboard'

urlpatterns = [
    path('', views.admin_dashboard, name='admin_dashboard'),
    path('inventory-logs/', views.admin_inventory_logs, name='inventory_logs'),
    path('users/', views.user_management, name='user_management'),
] 