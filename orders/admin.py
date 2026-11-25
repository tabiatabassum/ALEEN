
from decimal import Decimal

from django import forms
from django.contrib import admin
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils.html import format_html

from .models import Order, OrderItem, CustomizationRequest


class NormalOrderAdminForm(forms.ModelForm):

    class Meta:
        model = Order
        fields = '__all__'

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        if (
            self.instance.pk
            and self.instance.order_type != 'STORE_POS'
            and self.instance.delivery_type == 'NORMAL'
        ):

            if 'shipping_fee' in self.fields:

                self.fields['shipping_fee'].required = False

                self.fields['shipping_fee'].help_text = (
                    "Enter the delivery charge before confirming "
                    "the customer's order. Normal delivery in "
                    "Uttara is free."
                )

                if (
                    self.instance.status == 'PENDING'
                    and self.instance.shipping_fee == 0
                ):
                    self.initial['shipping_fee'] = None

    def clean(self):

        cleaned_data = super().clean()

        order_type = cleaned_data.get('order_type')
        delivery_type = cleaned_data.get('delivery_type')
        status = cleaned_data.get('status')

        if (
            self.instance.pk
            and order_type != 'STORE_POS'
            and delivery_type == 'NORMAL'
        ):

            previous_status = self.instance.status

            area = cleaned_data.get('area') or ''
            address = cleaned_data.get('address') or ''

            location_text = f"{area} {address}".lower()

            is_uttara = (
                'uttara' in location_text
                or 'উত্তরা' in location_text
            )

            shipping_fee = cleaned_data.get('shipping_fee')

            if is_uttara:

                cleaned_data['shipping_fee'] = Decimal('0.00')

            elif shipping_fee is None:

                if status in (
                    'CONFIRMED',
                    'PROCESSING',
                    'OUT_FOR_DELIVERY',
                    'DELIVERED',
                ):

                    self.add_error(
                        'shipping_fee',
                        'Please enter the delivery fee before '
                        'confirming this order.'
                    )

                else:

                    cleaned_data['shipping_fee'] = Decimal('0.00')

            elif shipping_fee < Decimal('0.00'):

                self.add_error(
                    'shipping_fee',
                    'Delivery fee cannot be negative.'
                )

            elif (
                shipping_fee == Decimal('0.00')
                and status in (
                    'CONFIRMED',
                    'PROCESSING',
                    'OUT_FOR_DELIVERY',
                    'DELIVERED',
                )
            ):

                self.add_error(
                    'shipping_fee',
                    'Free delivery is only available in Uttara. '
                    'Please enter a valid delivery fee.'
                )

            if (
                previous_status == 'PENDING'
                and status in (
                    'PROCESSING',
                    'OUT_FOR_DELIVERY',
                    'DELIVERED',
                )
            ):

                self.add_error(
                    'status',
                    'Please confirm this order before '
                    'proceeding with delivery.'
                )

        return cleaned_data


class OrderItemInline(admin.TabularInline):

    model = OrderItem
    extra = 0

    fields = (
        'product',
        'custom_item_name',
        'quantity',
        'unit_price',
        'unit_cost',
    )


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):

    form = NormalOrderAdminForm

    list_display = (
        'id',
        'order_type',
        'delivery_type',
        'customer_name',
        'phone',
        'area',
        'shipping_fee',
        'total_amount',
        'status',
        'emergency_status',
        'created_at',
    )

    list_filter = (
        'order_type',
        'delivery_type',
        'emergency_status',
        'status',
        'created_at',
    )

    search_fields = (
        'customer_name',
        'phone',
        'area',
        'address',
    )

    readonly_fields = ('created_at',)

    list_per_page = 25

    inlines = [OrderItemInline]

    fieldsets = (
        ('Order Information', {
            'fields': (
                'order_type',
                'status',
                'created_at',
            )
        }),

        ('Customer Information', {
            'fields': (
                'customer_name',
                'phone',
                'area',
                'address',
            )
        }),

        ('Delivery Settings', {
            'fields': (
                'delivery_type',
                'shipping_fee',
                'notes',
            )
        }),

        ('Emergency Delivery Management', {
            'fields': (
                'emergency_requested_time',
                'emergency_notes',
                'emergency_status',
                'emergency_charge',
                'stock_reserved',
            )
        }),

        ('Payment Summary', {
            'fields': (
                'discount_amount',
                'total_amount',
            )
        }),
    )

    def get_readonly_fields(self, request, obj=None):

        fields = list(
            super().get_readonly_fields(request, obj)
        )

        if (
            obj
            and obj.order_type != 'STORE_POS'
            and obj.delivery_type == 'NORMAL'
        ):

            fields.append('total_amount')

        return fields

    def save_model(self, request, obj, form, change):

        if not change:

            super().save_model(
                request, obj, form, change
            )

            return

        with transaction.atomic():

            old_order = (
                Order.objects.select_for_update()
                .get(pk=obj.pk)
            )

            previous_emergency_status = (
                old_order.emergency_status
            )

            previous_delivery_type = (
                old_order.delivery_type
            )

            if (
                old_order.delivery_type == 'EMERGENCY'
                and obj.delivery_type != 'EMERGENCY'
            ):

                raise ValidationError(
                    "An Emergency Delivery request cannot be "
                    "changed into a Normal Delivery order."
                )

            # EMERGENCY DELIVERY APPROVAL

            if (
                obj.delivery_type == 'EMERGENCY'
                and obj.emergency_status == 'APPROVED'
                and previous_emergency_status != 'APPROVED'
            ):

                if not old_order.stock_reserved:

                    raise ValidationError(
                        "Stock is not reserved for this request. "
                        "Please review it before approving."
                    )

                for item in old_order.items.select_related(
                    'product'
                ).all():

                    if item.product:

                        product = item.product

                        product.sales_count += item.quantity

                        product.save(
                            update_fields=['sales_count']
                        )

                obj.status = 'PROCESSING'

            # EMERGENCY DELIVERY DECLINE

            elif (
                obj.delivery_type == 'EMERGENCY'
                and obj.emergency_status == 'DECLINED'
                and previous_emergency_status != 'DECLINED'
            ):

                if old_order.stock_reserved:

                    for item in old_order.items.select_related(
                        'product'
                    ).all():

                        if item.product:

                            product = item.product

                            product.stock_qty += item.quantity

                            product.save(
                                update_fields=['stock_qty']
                            )

                    obj.stock_reserved = False

                obj.status = 'CANCELLED'

            elif (
                obj.delivery_type == 'EMERGENCY'
                and obj.emergency_status == 'APPROVED'
                and previous_emergency_status == 'DECLINED'
            ):

                raise ValidationError(
                    "A declined Emergency Delivery request "
                    "cannot be approved again."
                )

            # EMERGENCY PAYMENT CALCULATION

            if obj.delivery_type == 'EMERGENCY':

                obj.shipping_fee = obj.emergency_charge

                subtotal = sum(
                    (
                        item.subtotal
                        for item in old_order.items.all()
                    ),
                    Decimal('0.00')
                )

                obj.total_amount = (
                    max(
                        Decimal('0.00'),
                        subtotal - obj.discount_amount
                    )
                    + obj.emergency_charge
                )

            # NORMAL ONLINE DELIVERY

            elif (
                obj.order_type != 'STORE_POS'
                and obj.delivery_type == 'NORMAL'
            ):

                location_text = (
                    f"{obj.area} {obj.address}"
                ).lower()

                if (
                    'uttara' in location_text
                    or 'উত্তরা' in location_text
                ):

                    obj.shipping_fee = Decimal('0.00')

            super().save_model(
                request, obj, form, change
            )

    def save_related(
        self, request, form, formsets, change
    ):

        super().save_related(
            request, form, formsets, change
        )

        obj = form.instance

        # NORMAL ORDER FINAL PAYMENT CALCULATION

        if (
            obj.order_type != 'STORE_POS'
            and obj.delivery_type == 'NORMAL'
        ):

            subtotal = sum(
                (
                    item.subtotal
                    for item in obj.items.all()
                ),
                Decimal('0.00')
            )

            shipping_fee = (
                obj.shipping_fee or Decimal('0.00')
            )

            discount = (
                obj.discount_amount or Decimal('0.00')
            )

            location_text = (
                f"{obj.area} {obj.address}"
            ).lower()

            if (
                'uttara' in location_text
                or 'উত্তরা' in location_text
            ):

                shipping_fee = Decimal('0.00')

            obj.shipping_fee = shipping_fee

            obj.total_amount = (
                max(
                    Decimal('0.00'),
                    subtotal - discount
                )
                + shipping_fee
            )

            obj.save(
                update_fields=[
                    'shipping_fee',
                    'total_amount',
                ]
            )


@admin.register(CustomizationRequest)
class CustomizationRequestAdmin(admin.ModelAdmin):

    list_display = (
        'id',
        'customer_name',
        'phone',
        'is_contacted',
        'created_at',
    )

    list_filter = (
        'is_contacted',
        'created_at',
    )

    search_fields = (
        'customer_name',
        'phone',
        'address',
        'description',
    )

    readonly_fields = (
        'created_at',
        'reference_image_preview',
    )

    fields = (
        'customer_name',
        'phone',
        'address',
        'reference_image',
        'reference_image_preview',
        'description',
        'is_contacted',
        'created_at',
    )

    def reference_image_preview(self, obj):

        if obj.reference_image:

            return format_html(
                '<img src="{}" '
                'style="max-width:250px; max-height:250px; '
                'object-fit:contain;" />',
                obj.reference_image.url
            )

        return "No image uploaded"

    reference_image_preview.short_description = (
        "Reference Image Preview"
    )
