
from django.contrib import admin
from .models import Category, Product


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'parent', 'display_order')
    list_filter = ('parent',)
    search_fields = ('name',)
    ordering = ('display_order', 'name')


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):

    list_display = (
        'name',
        'category',
        'pricing_type',
        'selling_price',
        'discount_price',
        'discount_percentage_display',
        'stock_qty',
        'stock_status',
        'is_available',
        'is_hero_featured',
    )

    list_filter = (
        'category',
        'pricing_type',
        'is_available',
        'is_hero_featured',
    )

    search_fields = (
        'name',
        'category__name',
    )

    list_editable = (
        'selling_price',
        'discount_price',
        'stock_qty',
        'is_available',
        'is_hero_featured',
    )

    readonly_fields = (
        'slug',
        'sales_count',
        'created_at',
        'discount_percentage_display',
    )

    fieldsets = (
        ('Basic Information', {
            'fields': (
                'name',
                'slug',
                'category',
                'image',
                'short_description',
                'story_description',
            )
        }),
        ('Pricing', {
            'fields': (
                'pricing_type',
                'cost_price',
                'selling_price',
                'discount_price',
                'discount_percentage_display',
            )
        }),
        ('Inventory & Availability', {
            'fields': (
                'stock_qty',
                'is_available',
            )
        }),
        ('Homepage Display', {
            'fields': (
                'is_hero_featured',
            )
        }),
        ('Sales Information', {
            'fields': (
                'sales_count',
                'created_at',
            )
        }),
    )

    @admin.display(description='Discount %')
    def discount_percentage_display(self, obj):
        return f"{obj.discount_percentage}%"

    @admin.display(description='Stock Status')
    def stock_status(self, obj):
        return 'In Stock' if obj.is_in_stock else 'Out of Stock'
