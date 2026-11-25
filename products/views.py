
from django.shortcuts import render, get_object_or_404
from django.db.models import Q
from .models import Category, Product


def shop(request):
    categories = Category.objects.all()
    main_categories = categories.filter(parent__isnull=True)

    selected_slug = request.GET.get('category', '').strip()
    search_query = request.GET.get('q', '').strip()

    active_category = None
    active_parent = None
    subcategories = Category.objects.none()

    products = (
        Product.objects
        .filter(is_available=True)
        .select_related('category', 'category__parent')
        .order_by('-created_at')
    )

    if selected_slug:
        active_category = get_object_or_404(Category, slug=selected_slug)

        if active_category.parent:
            active_parent = active_category.parent
            subcategories = active_parent.subcategories.all()
            products = products.filter(category=active_category)

        else:
            active_parent = active_category
            subcategories = active_category.subcategories.all()

            if subcategories.exists():
                products = products.filter(
                    Q(category=active_category) |
                    Q(category__parent=active_category)
                )
            else:
                products = products.filter(category=active_category)

    if search_query:
        products = products.filter(
            Q(name__icontains=search_query) |
            Q(short_description__icontains=search_query)
        )

    context = {
        'categories': categories,
        'main_categories': main_categories,
        'active_category': active_category,
        'active_parent': active_parent,
        'subcategories': subcategories,
        'products': products,
        'search_query': search_query,
    }

    return render(request, 'products/shop.html', context)


def product_detail(request, slug):
    product = get_object_or_404(
        Product.objects.select_related('category'),
        slug=slug,
        is_available=True
    )

    related_products = (
        Product.objects.filter(
            category=product.category,
            is_available=True
        )
        .exclude(id=product.id)
        .order_by('-created_at')[:4]
    )

    context = {
        'product': product,
        'related_products': related_products,
    }

    return render(request, 'products/product_detail.html', context)
