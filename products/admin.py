
from django import forms
from django.contrib import admin
from django.forms.widgets import CheckboxSelectMultiple
from django.utils.html import format_html

from .models import Category, Product


# -----------------------------------
# SELECT ALL / DESELECT ALL WIDGET
# -----------------------------------

class SelectAllCheckboxSelectMultiple(CheckboxSelectMultiple):

    def render(self, name, value, attrs=None, renderer=None):
        checkbox_html = super().render(
            name, value, attrs, renderer
        )

        selected_values = set(value or [])
        all_values = {
            str(choice[0]) for choice in self.choices
        }

        all_selected = (
            bool(all_values)
            and all_values.issubset(selected_values)
        )

        button_label = (
            'Deselect All' if all_selected else 'Select All'
        )

        return format_html(
            '<div class="gift-checkbox-group">'
            '{}'
            '<button type="button" class="button" '
            'style="margin-top:8px;" '
            'onclick="'
            'var boxes=this.parentNode.querySelectorAll('
            '\'input[type=checkbox]\');'
            'var allChecked=Array.from(boxes).every('
            'box=>box.checked);'
            'boxes.forEach(box=>box.checked=!allChecked);'
            'this.textContent=allChecked?'
            '\'Select All\':\'Deselect All\';'
            '">'
            '{}'
            '</button>'
            '</div>',
            checkbox_html,
            button_label
        )


# -----------------------------------
# PRODUCT ADMIN FORM
# -----------------------------------

class ProductAdminForm(forms.ModelForm):

    gift_occasions = forms.MultipleChoiceField(
        choices=[
            ('birthday', 'Birthday'),
            ('anniversary', 'Anniversary'),
            ('valentines_day', "Valentine's Day"),
            ('congratulations', 'Congratulations'),
            ('thank_you', 'Thank You'),
            ('get_well_soon', 'Get Well Soon'),
            ('just_because', 'Just Because'),
        ],
        required=False,
        widget=SelectAllCheckboxSelectMultiple
    )

    gift_recipients = forms.MultipleChoiceField(
        choices=[
            ('mother', 'Mother'),
            ('father', 'Father'),
            ('sister', 'Sister'),
            ('brother', 'Brother'),
            ('friend', 'Friend'),
            ('partner', 'Partner'),
            ('colleague', 'Colleague'),
        ],
        required=False,
        widget=SelectAllCheckboxSelectMultiple
    )

    gift_budgets = forms.MultipleChoiceField(
        choices=[
            ('under_500', 'Under ৳500'),
            ('500_1000', '৳500 – ৳1,000'),
            ('1000_2000', '৳1,000 – ৳2,000'),
            ('2000_5000', '৳2,000 – ৳5,000'),
            ('5000_plus', '৳5,000+'),
        ],
        required=False,
        widget=CheckboxSelectMultiple
    )

    class Meta:
        model = Product
        fields = '__all__'


# -----------------------------------
# CATEGORY ADMIN
# -----------------------------------

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):

    list_display = (
        'name',
        'parent',
        'display_order',
    )

    list_filter = (
        'parent',
    )

    search_fields = (
        'name',
    )

    ordering = (
        'display_order',
        'name',
    )

    readonly_fields = (
        'slug',
    )

    fieldsets = (
        ('Category Information', {
            'fields': (
                'name',
                'slug',
                'parent',
                'image',
                'short_description',
                'display_order',
            )
        }),
    )


# -----------------------------------
# PRODUCT ADMIN
# -----------------------------------

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):

    form = ProductAdminForm

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

        ('Flower Meaning', {
            'fields': (
                'sentimental_description',
            )
        }),

        ('Flower Care Information', {
            'fields': (
                'flower_care',
            )
        }),

        ('Gift Finder Information', {
            'fields': (
                'gift_occasions',
                'gift_recipients',
                'gift_budgets',
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

    @admin.display(description='Discount')
    def discount_percentage_display(self, obj):

        if (
            obj
            and obj.selling_price
            and obj.discount_price
            and obj.discount_price < obj.selling_price
        ):
            discount = (
                (obj.selling_price - obj.discount_price)
                / obj.selling_price
            ) * 100

            return f'{discount:.0f}%'

        return '-'

    @admin.display(description='Stock Status')
    def stock_status(self, obj):

        if obj.stock_qty > 0:
            return 'In Stock'

        return 'Out of Stock'
