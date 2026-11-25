
import json
import calendar
from datetime import timedelta
from urllib.parse import urlencode
from decimal import Decimal, InvalidOperation

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, Http404
from django.core import signing
from django.views.decorators.cache import never_cache
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.contrib.auth import authenticate, login, logout
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.utils import timezone
from django.db import transaction
from django.db.models import (
    Sum, F, DecimalField, ExpressionWrapper,
    Case, When, Value, CharField, Q
)
from django.db.models.functions import Coalesce, ExtractMonth

from products.models import Product
from core.models import Coupon, SiteSettings
from .models import Order, OrderItem, CustomizationRequest
from .cart import Cart


# ==========================================
# CUSTOMER: CART API
# ==========================================

def cart_api(request):
    cart = Cart(request)
    return JsonResponse(cart.to_json())


@require_POST
def cart_add(request):

    try:
        data = json.loads(request.body)
        product_id = data.get('product_id')
        quantity = int(data.get('quantity', 1))

    except (ValueError, TypeError):
        return JsonResponse(
            {'error': 'Invalid request'},
            status=400
        )

    product = get_object_or_404(
        Product,
        id=product_id,
        is_available=True
    )

    if not product.is_in_stock:
        return JsonResponse(
            {'error': 'This bloom is currently sold out.'},
            status=400
        )

    cart = Cart(request)
    cart.add(product, max(1, quantity))

    return JsonResponse(cart.to_json())


@require_POST
def cart_update(request):

    try:
        data = json.loads(request.body)
        product_id = data.get('product_id')
        quantity = int(data.get('quantity', 0))

    except (ValueError, TypeError):
        return JsonResponse(
            {'error': 'Invalid request'},
            status=400
        )

    cart = Cart(request)

    if quantity <= 0:

        cart.remove(product_id)

    else:

        product = get_object_or_404(
            Product,
            id=product_id,
            is_available=True
        )

        cart.update(product, quantity)

    return JsonResponse(cart.to_json())


# ==========================================
# CUSTOMER: GUEST CHECKOUT
# NORMAL + EMERGENCY DELIVERY
# ==========================================

def checkout(request):

    cart = Cart(request)
    items = cart.get_items()

    if not items:
        return redirect('shop')

    delivery_type = request.GET.get(
        'delivery',
        request.POST.get('delivery_type', 'normal')
    ).lower()

    if delivery_type not in ('normal', 'emergency'):
        delivery_type = 'normal'

    is_emergency = delivery_type == 'emergency'

    site_settings = SiteSettings.objects.first()

    default_shipping = (
        site_settings.default_shipping_fee
        if site_settings
        else Decimal('80.00')
    )

    subtotal = cart.get_total_price()
    error_message = ''

    if request.method == 'POST':

        customer_name = request.POST.get(
            'customer_name', ''
        ).strip()

        phone = request.POST.get(
            'phone', ''
        ).strip()

        area = request.POST.get(
            'area', ''
        ).strip()

        address = request.POST.get(
            'address', ''
        ).strip()

        notes = request.POST.get(
            'notes', ''
        ).strip()

        coupon_code = request.POST.get(
            'coupon_code', ''
        ).strip()

        emergency_requested_time = request.POST.get(
            'emergency_requested_time', ''
        ).strip()

        emergency_notes = request.POST.get(
            'emergency_notes', ''
        ).strip()

        if not customer_name or not phone or not area or not address:

            error_message = (
                'Please complete all required delivery fields.'
            )

        elif is_emergency and not emergency_requested_time:

            error_message = (
                'Please tell us how soon you need the delivery.'
            )

        else:

            discount_amount = Decimal('0.00')

            # PROMO CODE VALIDATION

            if coupon_code:

                coupon = Coupon.objects.filter(
                    code__iexact=coupon_code,
                    is_active=True
                ).first()

                if (
                    coupon
                    and (
                        not coupon.valid_until
                        or coupon.valid_until >= timezone.now()
                    )
                ):

                    discount_amount = (
                        subtotal
                        * Decimal(coupon.discount_percent)
                        / Decimal('100')
                    ).quantize(Decimal('0.01'))

                else:

                    error_message = 'Invalid or expired promo code.'

            if not error_message:

                # Delivery fee will be determined by Admin.
                # Zero is a temporary value, not a confirmed fee.

                shipping_fee = Decimal('0.00')

                emergency_status = (
                    'REQUESTED'
                    if is_emergency
                    else 'NOT_APPLICABLE'
                )

                total_amount = max(
                    Decimal('0.00'),
                    subtotal - discount_amount
                ) + shipping_fee

                try:

                    with transaction.atomic():

                        # LOCK PRODUCTS AND VERIFY STOCK

                        locked_products = {}

                        for item in items:

                            product = (
                                Product.objects.select_for_update()
                                .get(id=item['product'].id)
                            )

                            if not product.is_available:

                                raise ValueError(
                                    f"{product.name} is currently unavailable."
                                )

                            quantity = int(item['quantity'])

                            if product.stock_qty < quantity:

                                raise ValueError(
                                    f"Only {product.stock_qty} "
                                    f"unit(s) of {product.name} are available."
                                )

                            locked_products[product.id] = product

                        # CREATE PENDING ONLINE ORDER

                        order = Order.objects.create(
                            order_type='ONLINE',
                            status='PENDING',

                            delivery_type=(
                                'EMERGENCY'
                                if is_emergency
                                else 'NORMAL'
                            ),

                            customer_name=customer_name,
                            phone=phone,
                            area=area,
                            address=address,

                            shipping_fee=shipping_fee,
                            discount_amount=discount_amount,
                            total_amount=total_amount,

                            notes=notes,

                            emergency_requested_time=(
                                emergency_requested_time
                                if is_emergency
                                else ''
                            ),

                            emergency_notes=(
                                emergency_notes
                                if is_emergency
                                else ''
                            ),

                            emergency_status=emergency_status,
                        )

                        # CREATE ORDER ITEMS

                        for item in items:

                            product = locked_products[
                                item['product'].id
                            ]

                            quantity = int(item['quantity'])

                            OrderItem.objects.create(
                                order=order,
                                product=product,
                                quantity=quantity,
                                unit_price=product.current_price,
                                unit_cost=product.cost_price,
                            )

                            # RESERVE STOCK

                            product.stock_qty -= quantity

                            # Preserve existing normal order sales logic.
                            # Emergency sales count increases on approval.

                            if not is_emergency:

                                product.sales_count += quantity

                            product.save(
                                update_fields=[
                                    'stock_qty',
                                    'sales_count',
                                ]
                            )

                        order.stock_reserved = True

                        order.save(
                            update_fields=['stock_reserved']
                        )

                    cart.clear()

                    # SECURE GUEST ORDER TRACKING LINK

                    tracking_token = signing.dumps(
                        order.id,
                        salt='aleen.order-tracking.v1'
                    )

                    tracking_url = reverse(
                        'order_success',
                        kwargs={'order_id': order.id}
                    )

                    return redirect(
                        f"{tracking_url}?"
                        f"{urlencode({'token': tracking_token})}"
                    )

                except ValueError as exc:

                    error_message = str(exc)

    context = {
        'items': items,
        'subtotal': subtotal,
        'default_shipping': default_shipping,
        'error_message': error_message,
        'delivery_type': delivery_type,
        'is_emergency': is_emergency,
    }

    return render(
        request,
        'orders/checkout.html',
        context
    )


# ==========================================
# CUSTOMER: SECURE ORDER STATUS PAGE
# ==========================================

@never_cache
def order_success(request, order_id):

    tracking_token = request.GET.get('token', '')

    try:

        signed_order_id = signing.loads(
            tracking_token,
            salt='aleen.order-tracking.v1'
        )

    except signing.BadSignature:

        raise Http404('Order not found.')

    if str(signed_order_id) != str(order_id):

        raise Http404('Order not found.')

    order = get_object_or_404(
        Order,
        id=order_id
    )

    order_subtotal = sum(
        (
            item.subtotal
            for item in order.items.all()
        ),
        Decimal('0.00')
    )

    context = {
        'order': order,
        'order_subtotal': order_subtotal,
    }

    response = render(
        request,
        'orders/order_success.html',
        context
    )

    response['Referrer-Policy'] = 'no-referrer'

    return response


# ==========================================
# PRIVATE STAFF PORTAL: LOGIN & LOGOUT
# ==========================================

def staff_login(request):

    if request.user.is_authenticated and request.user.is_staff:

        return redirect('store_pos')

    error = ''

    if request.method == 'POST':

        username = request.POST.get(
            'username', ''
        ).strip()

        password = request.POST.get(
            'password', ''
        )

        user = authenticate(
            request,
            username=username,
            password=password
        )

        if user is not None and user.is_active and user.is_staff:

            login(request, user)

            next_url = request.GET.get('next') or 'store_pos'

            return redirect(next_url)

        else:

            error = (
                "Invalid username or password, "
                "or your staff access is not enabled."
            )

    return render(
        request,
        'orders/staff_login.html',
        {'error': error}
    )


@require_POST
def staff_logout(request):

    logout(request)

    return redirect('staff_login')


# ==========================================
# STAFF PORTAL: QUICK IN-STORE SALE (POS)
# ==========================================

@staff_member_required(login_url='staff_login')
def store_pos(request):

    products = Product.objects.select_related(
        'category'
    ).order_by('name')

    if request.method == 'POST':

        customer_name = (
            request.POST.get(
                'customer_name', ''
            ).strip()
            or 'Walk-in Customer'
        )

        phone = (
            request.POST.get(
                'phone', ''
            ).strip()
            or 'N/A'
        )

        notes = request.POST.get(
            'notes', ''
        ).strip()

        product_ids = request.POST.getlist('product_id[]')
        custom_names = request.POST.getlist('custom_name[]')
        unit_costs = request.POST.getlist('unit_cost[]')
        unit_prices = request.POST.getlist('unit_price[]')
        quantities = request.POST.getlist('quantity[]')

        parsed_items = []
        error = None

        for pid, cname, cost_str, price_str, qty_str in zip(
            product_ids,
            custom_names,
            unit_costs,
            unit_prices,
            quantities
        ):

            if not pid:
                continue

            try:

                unit_price = Decimal(price_str.strip())
                qty = int(qty_str.strip())

                if unit_price <= 0 or qty <= 0:

                    error = (
                        "Selling price and quantity must be "
                        "greater than 0."
                    )

                    break

                if pid == 'CUSTOM':

                    clean_name = cname.strip()

                    if not clean_name:

                        error = (
                            "Please enter a name for the "
                            "Customised Bouquet or Bag."
                        )

                        break

                    unit_cost = (
                        Decimal(cost_str.strip())
                        if cost_str.strip()
                        else Decimal('0.00')
                    )

                    if unit_cost < 0:

                        error = "Making cost must be 0 or higher."

                        break

                    parsed_items.append(
                        (
                            None,
                            clean_name,
                            unit_cost,
                            unit_price,
                            qty
                        )
                    )

                else:

                    product = Product.objects.get(
                        id=int(pid)
                    )

                    unit_cost = (
                        Decimal(cost_str.strip())
                        if cost_str.strip()
                        else product.cost_price
                    )

                    if unit_cost < 0:

                        error = "Unit cost must be 0 or higher."

                        break

                    parsed_items.append(
                        (
                            product,
                            '',
                            unit_cost,
                            unit_price,
                            qty
                        )
                    )

            except (
                Product.DoesNotExist,
                ValueError,
                InvalidOperation
            ):

                error = (
                    "Please enter valid product, "
                    "price, and quantity values."
                )

                break

        if not parsed_items and not error:

            error = (
                "Please add at least 1 product "
                "or customised item."
            )

        if error:

            messages.error(request, error)

        else:

            grand_total = sum(
                (
                    price * qty
                    for _, _, _, price, qty in parsed_items
                ),
                Decimal('0.00')
            )

            with transaction.atomic():

                order = Order.objects.create(
                    order_type='STORE_POS',
                    delivery_type='NORMAL',
                    customer_name=customer_name,
                    phone=phone,
                    area='In-Store',
                    shipping_fee=Decimal('0.00'),
                    discount_amount=Decimal('0.00'),
                    total_amount=grand_total,
                    status='DELIVERED',
                    notes=notes,
                )

                for product, cname, unit_cost, unit_price, qty in parsed_items:

                    OrderItem.objects.create(
                        order=order,
                        product=product,
                        custom_item_name=cname,
                        quantity=qty,
                        unit_price=unit_price,
                        unit_cost=unit_cost,
                    )

                    if product:

                        product.stock_qty = max(
                            0,
                            product.stock_qty - qty
                        )

                        product.sales_count += qty

                        product.save(
                            update_fields=[
                                'stock_qty',
                                'sales_count',
                            ]
                        )

            messages.success(
                request,
                f"Store sale #{order.id} saved successfully! "
                f"Grand Total: ৳{grand_total}"
            )

            return redirect('store_pos')

    recent_pos_orders = (
        Order.objects.filter(
            order_type='STORE_POS'
        )
        .prefetch_related('items__product')
        .order_by('-created_at')[:10]
    )

    return render(
        request,
        'orders/store_pos.html',
        {
            'products': products,
            'recent_pos_orders': recent_pos_orders,
        }
    )


# ==========================================
# STAFF & ADMIN: SALES DASHBOARD
# DAILY / WEEKLY / MONTHLY / YEARLY
# ==========================================

@staff_member_required(login_url='staff_login')
def sales_dashboard(request):

    now = timezone.localtime(timezone.now())

    active_range = request.GET.get(
        'range', 'month'
    )

    try:

        selected_year = int(
            request.GET.get('year', now.year)
        )

    except ValueError:

        selected_year = now.year

    selected_month = request.GET.get(
        'month',
        str(now.month)
    )

    selected_month_int = now.month

    if selected_month != 'all':

        try:

            m_val = int(selected_month)

            if 1 <= m_val <= 12:

                selected_month_int = m_val

        except ValueError:

            pass

    existing_years = list(
        Order.objects.dates(
            'created_at',
            'year'
        ).values_list(
            'created_at__year',
            flat=True
        )
    )

    available_years = sorted(
        set(existing_years + [now.year]),
        reverse=True
    )

    # Pending and cancelled orders are excluded.
    # Emergency requests must be approved.

    base_orders = (
        Order.objects.exclude(
            status__in=('PENDING', 'CANCELLED')
        )
        .filter(
            ~Q(delivery_type='EMERGENCY')
            | Q(emergency_status='APPROVED')
        )
    )

    # TODAY

    if active_range == 'today':

        start_today = now.replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0
        )

        period_orders = base_orders.filter(
            created_at__gte=start_today
        )

        period_label = (
            f"Today ({now.strftime('%d %b %Y')})"
        )

        selected_year = now.year
        selected_month = str(now.month)

    # THIS WEEK

    elif active_range == 'week':

        start_week = (
            now - timedelta(days=6)
        ).replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0
        )

        period_orders = base_orders.filter(
            created_at__gte=start_week
        )

        period_label = (
            f"This Week ({start_week.strftime('%d %b')} "
            f"– {now.strftime('%d %b %Y')})"
        )

        selected_year = now.year
        selected_month = str(now.month)

    # FULL YEAR

    elif active_range == 'year':

        period_orders = base_orders.filter(
            created_at__year=selected_year
        )

        period_label = (
            f"Full Year {selected_year}"
        )

        selected_month = 'all'

    # CUSTOM PERIOD

    elif active_range == 'custom':

        if selected_month == 'all':

            period_orders = base_orders.filter(
                created_at__year=selected_year
            )

            period_label = (
                f"Full Year {selected_year}"
            )

        else:

            period_orders = base_orders.filter(
                created_at__year=selected_year,
                created_at__month=selected_month_int
            )

            period_label = (
                f"{calendar.month_name[selected_month_int]} "
                f"{selected_year}"
            )

    # CURRENT MONTH

    else:

        active_range = 'month'

        period_orders = base_orders.filter(
            created_at__year=now.year,
            created_at__month=now.month
        )

        period_label = (
            f"{calendar.month_name[now.month]} {now.year}"
        )

        selected_year = now.year
        selected_month = str(now.month)

    period_items = OrderItem.objects.filter(
        order__in=period_orders
    )

    net_order_expr = ExpressionWrapper(
        F('total_amount') - F('shipping_fee'),
        output_field=DecimalField(
            max_digits=12,
            decimal_places=2
        )
    )

    item_rev_expr = ExpressionWrapper(
        F('unit_price') * F('quantity'),
        output_field=DecimalField(
            max_digits=12,
            decimal_places=2
        )
    )

    item_cost_expr = ExpressionWrapper(
        F('unit_cost') * F('quantity'),
        output_field=DecimalField(
            max_digits=12,
            decimal_places=2
        )
    )

    # ONLINE REVENUE

    online_revenue = period_orders.filter(
        order_type='ONLINE'
    ).aggregate(
        total=Coalesce(
            Sum(net_order_expr),
            Decimal('0.00')
        )
    )['total']

    # STORE REVENUE

    store_revenue = period_orders.filter(
        order_type='STORE_POS'
    ).aggregate(
        total=Coalesce(
            Sum(net_order_expr),
            Decimal('0.00')
        )
    )['total']

    total_revenue = (
        online_revenue + store_revenue
    )

    total_cost = period_items.aggregate(
        total=Coalesce(
            Sum(item_cost_expr),
            Decimal('0.00')
        )
    )['total']

    net_profit = total_revenue - total_cost

    total_orders_count = period_orders.count()

    total_items_sold = period_items.aggregate(
        total=Coalesce(
            Sum('quantity'), 0
        )
    )['total']

    # TOP SELLING PRODUCTS

    top_products = (
        period_items.annotate(

            item_title=Case(
                When(
                    product__isnull=False,
                    then=F('product__name')
                ),
                default=F('custom_item_name'),
                output_field=CharField(),
            ),

            item_cat=Case(
                When(
                    product__isnull=False,
                    then=F('product__category__name')
                ),
                default=Value('Customised Order'),
                output_field=CharField(),
            ),

        )
        .values(
            'item_title',
            'item_cat'
        )
        .annotate(
            qty_sold=Sum('quantity'),
            revenue=Sum(item_rev_expr),
            cost=Sum(item_cost_expr),
        )
        .order_by(
            '-qty_sold',
            '-revenue'
        )[:10]
    )

    for row in top_products:

        row['profit'] = (
            (row['revenue'] or Decimal('0.00'))
            - (row['cost'] or Decimal('0.00'))
        )

    # YEARLY BREAKDOWN

    year_orders = base_orders.filter(
        created_at__year=selected_year
    )

    monthly_order_stats = (
        year_orders.annotate(
            m=ExtractMonth('created_at')
        )
        .values(
            'm',
            'order_type'
        )
        .annotate(
            rev=Coalesce(
                Sum(net_order_expr),
                Decimal('0.00')
            )
        )
    )

    monthly_cost_stats = (
        OrderItem.objects.filter(
            order__in=year_orders
        )
        .annotate(
            m=ExtractMonth('order__created_at')
        )
        .values('m')
        .annotate(
            cost=Coalesce(
                Sum(item_cost_expr),
                Decimal('0.00')
            )
        )
    )

    month_map = {

        m: {
            'month_num': m,
            'month_name': calendar.month_name[m],
            'online': Decimal('0.00'),
            'store': Decimal('0.00'),
            'cost': Decimal('0.00'),
        }

        for m in range(1, 13)
    }

    for row in monthly_order_stats:

        m = row['m']

        if row['order_type'] == 'ONLINE':

            month_map[m]['online'] = row['rev']

        else:

            month_map[m]['store'] = row['rev']

    for row in monthly_cost_stats:

        month_map[row['m']]['cost'] = row['cost']

    yearly_breakdown = []

    for m in range(1, 13):

        data = month_map[m]

        data['total'] = (
            data['online'] + data['store']
        )

        data['profit'] = (
            data['total'] - data['cost']
        )

        yearly_breakdown.append(data)

    context = {
        'active_range': active_range,
        'selected_year': selected_year,
        'selected_month': selected_month,
        'available_years': available_years,

        'months': [
            (str(m), calendar.month_name[m])
            for m in range(1, 13)
        ],

        'period_label': period_label,
        'online_revenue': online_revenue,
        'store_revenue': store_revenue,
        'total_revenue': total_revenue,
        'total_cost': total_cost,
        'net_profit': net_profit,
        'total_orders_count': total_orders_count,
        'total_items_sold': total_items_sold,
        'top_products': top_products,
        'yearly_breakdown': yearly_breakdown,
        'is_admin': request.user.is_superuser,
    }

    return render(
        request,
        'orders/sales_dashboard.html',
        context
    )


# ==========================================
# CUSTOMER: CUSTOMIZATION REQUEST
# ==========================================

def customize_order(request):

    error_message = ''

    submitted = (
        request.GET.get('submitted') == '1'
    )

    ref_id = request.GET.get('ref', '')

    if request.method == 'POST':

        customer_name = request.POST.get(
            'customer_name', ''
        ).strip()

        phone = request.POST.get(
            'phone', ''
        ).strip()

        address = request.POST.get(
            'address', ''
        ).strip()

        description = request.POST.get(
            'description', ''
        ).strip()

        reference_image = request.FILES.get(
            'reference_image'
        )

        if (
            not customer_name
            or not phone
            or not address
            or not reference_image
        ):

            error_message = (
                'Please fill in your name, phone number, '
                'delivery address, and upload a reference photo.'
            )

        else:

            custom_req = CustomizationRequest.objects.create(
                customer_name=customer_name,
                phone=phone,
                address=address,
                reference_image=reference_image,
                description=description,
            )

            return redirect(
                f"{reverse('customize_order')}"
                f"?submitted=1&ref={custom_req.id}"
            )

    return render(
        request,
        'orders/customize.html',
        {
            'error_message': error_message,
            'submitted': submitted,
            'ref_id': ref_id,
        }
    )
