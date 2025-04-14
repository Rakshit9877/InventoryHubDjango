from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Count, Case, When, F, Value, FloatField, Sum, Q
from django.db.models.functions import Coalesce
from django.contrib import messages
from django.http import JsonResponse
from inventory.models import Item, InventoryLog
from accounts.models import UserProfile
from django.utils import timezone
from functools import wraps

def admin_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_staff and not request.user.is_superuser:
            messages.error(request, "Access denied: Admin privileges required for this operation.")
            return redirect('inventory:dashboard')
        return view_func(request, *args, **kwargs)
    return _wrapped_view

@login_required
@admin_required
def admin_dashboard(request):
    # User statistics
    total_users = User.objects.count()
    admin_users = User.objects.filter(Q(is_staff=True) | Q(is_superuser=True)).count()
    regular_users = total_users - admin_users
    
    # Get recent users with their profiles
    recent_users = []
    for user in User.objects.order_by('-last_login')[:5]:
        user_data = {
            'username': user.username,
            'last_login': user.last_login.strftime('%Y-%m-%d %H:%M:%S') if user.last_login else 'Never',
            'email': user.email,
            'country': user.profile.country if hasattr(user, 'profile') else 'Unknown'
        }
        recent_users.append(user_data)
    
    # Inventory statistics
    total_items = Item.objects.count()
    total_inventory_value = Item.objects.aggregate(
        total=Coalesce(Sum(F('cost_price') * F('quantity_in_hand')), 0.0, output_field=FloatField())
    )['total']
    
    low_stock_items = Item.objects.filter(quantity_in_hand__lte=F('reorder_point')).count()
    out_of_stock_items = Item.objects.filter(quantity_in_hand=0).count()
    
    # High value items
    high_value_items = []
    for item in Item.objects.filter(cost_price__isnull=False).order_by('-cost_price')[:5]:
        high_value_items.append({
            'name': item.name,
            'cost_price': float(item.cost_price) if item.cost_price else 0,
            'quantity': item.quantity_in_hand
        })
    
    # User distribution by country
    user_by_country = []
    country_counts = UserProfile.objects.values('country').annotate(count=Count('id'))
    for data in country_counts:
        user_by_country.append({
            'country': data['country'] or 'Not Specified',
            'count': data['count']
        })
    
    # Price distribution
    price_ranges = [
        (0, 100, '0-100'),
        (101, 500, '101-500'),
        (501, 1000, '501-1000'),
        (1001, float('inf'), '1000+')
    ]
    
    price_distribution = []
    for min_price, max_price, label in price_ranges:
        if max_price == float('inf'):
            count = Item.objects.filter(selling_price__gt=min_price).count()
        else:
            count = Item.objects.filter(selling_price__gte=min_price, selling_price__lte=max_price).count()
        price_distribution.append({'range': label, 'count': count})
    
    return render(
        request, 
        'admin_dashboard/admin_dashboard.html',
        {
            'total_users': total_users,
            'admin_users': admin_users,
            'regular_users': regular_users,
            'recent_users': recent_users,
            'total_items': total_items,
            'total_inventory_value': total_inventory_value,
            'low_stock_items': low_stock_items,
            'out_of_stock_items': out_of_stock_items,
            'high_value_items': high_value_items,
            'user_by_country': user_by_country,
            'price_distribution': price_distribution
        }
    )

@login_required
@admin_required
def admin_inventory_logs(request):
    logs = InventoryLog.objects.order_by('-timestamp')[:10]
    log_data = [{
        'item': log.item.name,
        'user': log.user.username,
        'action': log.action,
        'quantity': log.quantity,
        'timestamp': log.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
        'notes': log.notes
    } for log in logs]
    
    return JsonResponse(log_data, safe=False)

@login_required
@admin_required
def user_management(request):
    users = User.objects.all().order_by('-date_joined')
    
    return render(
        request, 
        'admin_dashboard/user_management.html',
        {'users': users}
    )
