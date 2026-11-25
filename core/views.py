
from decimal import Decimal, InvalidOperation

from django.shortcuts import render, redirect
from django.utils import timezone
from django.db.models import Sum, Q, F

from products.models import Category, Product
from core.models import HeroSlide, BannerAd, Review, SiteSettings, StoreMemory
from orders.models import OrderItem


def home(request):
    now = timezone.localtime(timezone.now())

    hero_slides = HeroSlide.objects.filter(
        is_active=True
    ).order_by('display_order', 'id')

    hero_slides_data = [
        {
            'name': slide.name,
            'image': slide.image.url if slide.image else '',
            'left_description': slide.left_description,
            'right_description': slide.right_description,
        }
        for slide in hero_slides
    ]

    active_banners = BannerAd.objects.filter(
        is_active=True
    ).order_by('-created_at')[:5]

    categories = Category.objects.filter(
        parent__isnull=True
    ).order_by('display_order')[:4]

    monthly_top_rows = (
        OrderItem.objects.filter(
            order__created_at__year=now.year,
            order__created_at__month=now.month,
            product__isnull=False,
            product__is_available=True,
        )
        .exclude(order__status='CANCELLED')
        .values('product_id')
        .annotate(month_qty=Sum('quantity'))
        .order_by('-month_qty')[:8]
    )

    top_ids = [row['product_id'] for row in monthly_top_rows]
    product_map = Product.objects.in_bulk(top_ids)

    most_loved = [
        product_map[pid]
        for pid in top_ids
        if pid in product_map
    ]

    if len(most_loved) < 8:
        remaining = 8 - len(most_loved)

        fallback_products = list(
            Product.objects.filter(is_available=True)
            .exclude(id__in=top_ids)
            .order_by('-sales_count', '-created_at')[:remaining]
        )

        most_loved.extend(fallback_products)

    reviews = Review.objects.filter(
        is_approved=True
    ).order_by('-created_at')[:6]

    site_settings = SiteSettings.objects.first()

    context = {
        'hero_slides_data': hero_slides_data,
        'active_banners': active_banners,
        'categories': categories,
        'most_loved': most_loved,
        'current_month': now.strftime('%B'),
        'reviews': reviews,
        'site_settings': site_settings,
    }

    return render(request, 'core/home.html', context)


def atelier(request):
    store_memories = StoreMemory.objects.all().order_by('-created_at')

    approved_reviews = Review.objects.filter(
        is_approved=True
    ).order_by('-created_at')

    form_error = ''

    if request.method == 'POST':
        customer_name = request.POST.get('customer_name', '').strip()
        comment = request.POST.get('comment', '').strip()
        photo = request.FILES.get('photo')

        try:
            rating = int(request.POST.get('rating', 5))
            rating = max(1, min(rating, 5))
        except (TypeError, ValueError):
            rating = 5

        if not customer_name:
            form_error = 'Please enter your name.'

        elif not comment and not photo:
            form_error = 'Please upload a photo or write a review.'

        else:
            Review.objects.create(
                customer_name=customer_name,
                rating=rating,
                comment=comment,
                photo=photo,
                source='WEBSITE',
                is_approved=False
            )

            return redirect('/the-atelier/?submitted=1')

    context = {
        'store_memories': store_memories,
        'approved_reviews': approved_reviews,
        'form_error': form_error,
        'submitted': request.GET.get('submitted') == '1',
        'site_settings': SiteSettings.objects.first(),
    }

    return render(request, 'core/atelier.html', context)


def gift_finder(request):
    occasion = request.GET.get('occasion', '').strip()
    recipient = request.GET.get('recipient', '').strip()
    min_price = request.GET.get('min_price', '').strip()
    max_price = request.GET.get('max_price', '').strip()

    products = Product.objects.none()
    error_message = ''
    selected_budget = ''

    if request.GET:
        if not all([occasion, recipient, min_price, max_price]):
            error_message = 'Please complete all three steps.'

        else:
            try:
                minimum = Decimal(min_price)
                maximum = Decimal(max_price)

                if minimum < 0 or maximum < minimum:
                    raise ValueError

                if minimum == Decimal('0') and maximum == Decimal('500'):
                    selected_budget = 'under_500'

                elif minimum == Decimal('500') and maximum == Decimal('1000'):
                    selected_budget = '500_1000'

                elif minimum == Decimal('1000') and maximum == Decimal('2000'):
                    selected_budget = '1000_2000'

                elif minimum == Decimal('2000') and maximum == Decimal('5000'):
                    selected_budget = '2000_5000'

                elif minimum == Decimal('5000'):
                    selected_budget = '5000_plus'

                else:
                    raise ValueError

                discounted_price_filter = (
                    Q(discount_price__lt=F('selling_price')) &
                    Q(discount_price__gte=minimum)
                )

                regular_price_filter = (
                    (
                        Q(discount_price__isnull=True) |
                        Q(discount_price__gte=F('selling_price'))
                    ) &
                    Q(selling_price__gte=minimum)
                )

                if selected_budget != '5000_plus':
                    discounted_price_filter &= Q(
                        discount_price__lte=maximum
                    )

                    regular_price_filter &= Q(
                        selling_price__lte=maximum
                    )

                price_filter = (
                    discounted_price_filter |
                    regular_price_filter
                )

                products = Product.objects.filter(
                    is_available=True,
                    stock_qty__gt=0,
                    gift_occasions__contains=[occasion],
                    gift_recipients__contains=[recipient],
                    gift_budgets__contains=[selected_budget],
                ).filter(
                    price_filter
                ).order_by(
                    '-sales_count',
                    '-created_at'
                )

            except (InvalidOperation, ValueError):
                error_message = 'Please select a valid budget range.'

    context = {
        'products': products,
        'occasion': occasion,
        'recipient': recipient,
        'min_price': min_price,
        'max_price': max_price,
        'selected_budget': selected_budget,
        'error_message': error_message,
        'has_searched': bool(request.GET),
    }

    return render(
        request,
        'core/gift_finder_results.html',
        context
    )
