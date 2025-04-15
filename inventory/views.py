from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Case, When, F, Count, Q, Value, FloatField, ExpressionWrapper
from django.db.models.functions import Coalesce
from .models import Item, Group, GroupAttribute, InventoryLog
from .forms import ItemForm, GroupForm, GroupAttributeFormSet, InventoryLogForm
from django.utils import timezone
from django.http import JsonResponse
import datetime

@login_required
def inventory_home(request):
    messages.info(request, "Viewing inventory management section.")
    return render(request, 'inventory/inventory.html')

@login_required
def dashboard(request):
    # Count statistics
    total_items = Item.objects.count()
    total_inventory_value = Item.objects.aggregate(
        total=Coalesce(Sum(F('cost_price') * F('quantity_in_hand')), 0.0, output_field=FloatField())
    )['total']
    
    avg_item_value = total_inventory_value / total_items if total_items > 0 else 0
    low_stock_items = Item.objects.filter(quantity_in_hand__lte=F('reorder_point')).count()
    out_of_stock_items = Item.objects.filter(quantity_in_hand=0).count()
    items_to_receive = Item.objects.filter(quantity_to_receive__gt=0).count()
    high_value_items = Item.objects.filter(cost_price__gt=1000).count()
    returnable_items = Item.objects.filter(returnable=True).count()
    non_returnable_items = Item.objects.filter(returnable=False).count()

    # Calculate placeholder growth values for demonstration
    items_growth = 5.3  # placeholder growth percentage
    value_growth = 7.8  # placeholder growth percentage

    # Get top value items with calculated total_value
    top_value_items = Item.objects.filter(
        cost_price__isnull=False, 
        quantity_in_hand__gt=0
    ).annotate(
        calculated_value=ExpressionWrapper(
            F('cost_price') * F('quantity_in_hand'), 
            output_field=FloatField()
        )
    ).order_by('-calculated_value')[:5]

    # Calculate top margin items
    top_margin_items = Item.objects.filter(
        cost_price__isnull=False,
        selling_price__isnull=False,
        cost_price__gt=0
    ).annotate(
        calculated_margin=ExpressionWrapper(
            (F('selling_price') - F('cost_price')) * 100 / F('cost_price'),
            output_field=FloatField()
        )
    ).order_by('-calculated_margin')[:5]

    # Group statistics
    total_groups = Group.objects.count()
    goods_groups = Group.objects.filter(type='goods').count()
    service_groups = Group.objects.filter(type='service').count()
    returnable_groups = Group.objects.filter(returnable=True).count()
    recent_groups = Group.objects.order_by('-created_at')[:5]

    # Unit distribution
    unit_distribution = Group.objects.values('unit').annotate(count=Count('id'))

    # Groups with most attributes
    groups_with_attributes = Group.objects.annotate(
        attribute_count=Count('attributes')
    ).order_by('-attribute_count')[:5]

    # Group counts for chart
    group_counts = []
    if total_groups > 0:
        group_counts.append({
            'name': 'Goods',
            'count': goods_groups,
            'percentage': (goods_groups / total_groups) * 100 if total_groups > 0 else 0
        })
        group_counts.append({
            'name': 'Services',
            'count': service_groups,
            'percentage': (service_groups / total_groups) * 100 if total_groups > 0 else 0
        })
        group_counts.append({
            'name': 'Returnable',
            'count': returnable_groups,
            'percentage': (returnable_groups / total_groups) * 100 if total_groups > 0 else 0
        })

    return render(
        request, 
        'inventory/dashboard.html',
        {
            'total_items': total_items,
            'total_inventory_value': total_inventory_value,
            'avg_item_value': avg_item_value,
            'low_stock_items': low_stock_items,
            'out_of_stock_items': out_of_stock_items,
            'items_to_receive': items_to_receive,
            'high_value_items': high_value_items,
            'returnable_items': returnable_items,
            'non_returnable_items': non_returnable_items,
            'top_value_items': top_value_items,
            'top_margin_items': top_margin_items,
            'total_groups': total_groups,
            'goods_groups': goods_groups,
            'service_groups': service_groups,
            'returnable_groups': returnable_groups,
            'recent_groups': recent_groups,
            'unit_distribution': unit_distribution,
            'groups_with_attributes': groups_with_attributes,
            'group_counts': group_counts,
            'items_growth': items_growth,
            'value_growth': value_growth,
            'current_date': datetime.datetime.now(),
        }
    )

@login_required
def add_item(request):
    if request.method == 'POST':
        form = ItemForm(request.POST)
        if form.is_valid():
            item = form.save()
            messages.success(request, f"Item '{item.name}' has been added successfully!")
            
            # Log the item creation
            InventoryLog.objects.create(
                item=item,
                user=request.user,
                action='add',
                quantity=item.quantity_in_hand,
                notes=f"Initial creation with {item.quantity_in_hand} units"
            )
            
            return redirect('inventory:dashboard')
    else:
        form = ItemForm()
    
    return render(request, 'inventory/item_form.html', {'form': form})

@login_required
def item_list(request):
    items = Item.objects.all()
    total_items = items.count()
    total_value = items.filter(selling_price__isnull=False).aggregate(
        total=Coalesce(Sum('selling_price'), 0.0, output_field=FloatField())
    )['total']
    
    item_types = {
        "Goods": total_items
    }
    
    messages.info(request, f"Viewing list of {total_items} items.")
    return render(
        request,
        'inventory/item_list.html',
        {
            'items': items,
            'total_items': total_items,
            'total_value': total_value,
            'item_types': item_types,
        }
    )

@login_required
def delete_item(request, item_id):
    item = get_object_or_404(Item, id=item_id)
    item_name = item.name
    
    if request.method == 'POST':
        item.delete()
        messages.success(request, f"Item '{item_name}' has been deleted successfully.")
        return redirect('inventory:item_list')
    
    return render(request, 'inventory/confirm_delete.html', {'item': item})

@login_required
def update_item(request, item_id):
    item = get_object_or_404(Item, id=item_id)
    
    if request.method == 'POST':
        form = ItemForm(request.POST, instance=item)
        if form.is_valid():
            form.save()
            messages.success(request, f"Item '{item.name}' has been updated successfully!")
            return redirect('inventory:item_list')
    else:
        form = ItemForm(instance=item)
    
    return render(request, 'inventory/item_form.html', {'form': form, 'item': item})

@login_required
def group_list(request):
    type_filter = request.GET.get('typeFilter')
    returnable_filter = request.GET.get('returnableFilter')
    sort_by = request.GET.get('sortBy', 'created_at')
    sort_order = request.GET.get('sortOrder', 'desc')
    
    groups = Group.objects.all()
    
    if type_filter:
        groups = groups.filter(type=type_filter)
    
    if returnable_filter:
        returnable_value = returnable_filter.lower() == 'true'
        groups = groups.filter(returnable=returnable_value)
    
    if sort_by == 'name':
        order_by = F('name')
    else:  # Default to created_at
        order_by = F('created_at')
    
    if sort_order == 'desc':
        groups = groups.order_by(-order_by)
    else:
        groups = groups.order_by(order_by)
    
    return render(request, 'inventory/group_list.html', {'groups': groups})

@login_required
def add_group(request):
    if request.method == 'POST':
        form = GroupForm(request.POST)
        if form.is_valid():
            group = form.save(commit=False)
            group.created_by = request.user
            group.save()
            
            formset = GroupAttributeFormSet(request.POST, instance=group)
            if formset.is_valid():
                formset.save()
                
                messages.success(request, f"Item group '{group.name}' has been added successfully!")
                return redirect('inventory:group_list')
    else:
        form = GroupForm()
        formset = GroupAttributeFormSet(instance=Group())
    
    return render(request, 'inventory/group_form.html', {'form': form, 'attributes_formset': formset})

@login_required
def edit_group(request, group_id):
    group = get_object_or_404(Group, id=group_id)
    
    if request.method == 'POST':
        form = GroupForm(request.POST, instance=group)
        if form.is_valid():
            group = form.save()
            
            formset = GroupAttributeFormSet(request.POST, instance=group)
            if formset.is_valid():
                formset.save()
                
                messages.success(request, f"Item group '{group.name}' has been updated successfully!")
                return redirect('inventory:group_list')
    else:
        form = GroupForm(instance=group)
        formset = GroupAttributeFormSet(instance=group)
    
    return render(request, 'inventory/group_form.html', {'form': form, 'attributes_formset': formset})

@login_required
def delete_group(request, group_id):
    group = get_object_or_404(Group, id=group_id)
    
    # Check if group has items
    if Item.objects.filter(group=group).exists():
        messages.error(request, f"Cannot delete group '{group.name}' as it has items associated with it.")
        return redirect('inventory:group_list')
    
    if request.method == 'POST':
        group_name = group.name
        group.delete()
        messages.success(request, f"Item group '{group_name}' has been deleted successfully!")
        return redirect('inventory:group_list')
    
    return render(request, 'inventory/confirm_delete.html', {'group': group})

@login_required
def group_attributes_api(request, group_id):
    group = get_object_or_404(Group, id=group_id)
    attributes = group.attributes.all()
    
    # Convert attributes to list of dictionaries
    attributes_data = [
        {
            'id': attr.id,
            'name': attr.name,
            'value': attr.value,
        }
        for attr in attributes
    ]
    
    return JsonResponse(attributes_data, safe=False)

def about(request):
    page_title = "About InventoryHub"
    page_content = """
    InventoryHub is a comprehensive inventory management system designed to help businesses 
    track their inventory, manage items and categories, and monitor inventory movements.
    """
    
    return render(request, 'about.html', {
        'page_title': page_title,
        'page_content': page_content
    })
