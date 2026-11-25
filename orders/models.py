
from django.db import models
from products.models import Product


class Order(models.Model):

    ORDER_TYPE_CHOICES = [
        ('ONLINE', 'Online Order'),
        ('STORE_POS', 'Store POS Order'),
    ]

    STATUS_CHOICES = [
    ('PENDING', 'Pending'),
    ('CONFIRMED', 'Confirmed'),
    ('PROCESSING', 'Processing'),
    ('OUT_FOR_DELIVERY', 'Out for Delivery'),
    ('DELIVERED', 'Delivered'),
    ('CANCELLED', 'Cancelled'),
]

    DELIVERY_TYPE_CHOICES = [
        ('NORMAL', 'Normal Delivery'),
        ('EMERGENCY', 'Emergency Delivery'),
    ]

    EMERGENCY_STATUS_CHOICES = [
        ('NOT_APPLICABLE', 'Not Applicable'),
        ('REQUESTED', 'Request Received'),
        ('APPROVED', 'Approved'),
        ('DECLINED', 'Declined'),
    ]

    order_type = models.CharField(
        max_length=20,
        choices=ORDER_TYPE_CHOICES,
        default='ONLINE'
    )

    delivery_type = models.CharField(
        max_length=20,
        choices=DELIVERY_TYPE_CHOICES,
        default='NORMAL'
    )

    customer_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20)

    address = models.TextField(blank=True)

    area = models.CharField(
        max_length=100,
        blank=True,
        help_text="যেমন: Uttara, Dhanmondi, Banani"
    )

    shipping_fee = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=80.00
    )

    discount_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00
    )

    total_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING'
    )

    notes = models.TextField(blank=True)

    emergency_requested_time = models.CharField(
        max_length=100,
        blank=True,
        help_text="Customer requested delivery time"
    )

    emergency_notes = models.TextField(
        blank=True,
        help_text="Additional emergency delivery instructions"
    )

    emergency_status = models.CharField(
        max_length=20,
        choices=EMERGENCY_STATUS_CHOICES,
        default='NOT_APPLICABLE'
    )

    emergency_charge = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0.00
    )

    stock_reserved = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        location_text = f"{self.area} {self.address}".lower()

        if self.order_type == 'STORE_POS':
            self.shipping_fee = 0.00

        elif self.delivery_type == 'EMERGENCY':
            self.shipping_fee = self.emergency_charge

        elif 'uttara' in location_text or 'উত্তরা' in location_text:
            self.shipping_fee = 0.00

        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"#{self.id} - {self.customer_name} "
            f"({self.get_order_type_display()})"
        )


class OrderItem(models.Model):

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='items'
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    custom_item_name = models.CharField(
        max_length=200,
        blank=True,
        help_text="Custom POS item name if no product is selected"
    )

    quantity = models.PositiveIntegerField(default=1)

    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True
    )

    unit_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        default=0.00
    )

    def save(self, *args, **kwargs):
        if self.product:
            if self.unit_price is None:
                self.unit_price = self.product.current_price

            if self.unit_cost is None:
                self.unit_cost = self.product.cost_price

        super().save(*args, **kwargs)

    @property
    def display_name(self):
        if self.product:
            return self.product.name
        return self.custom_item_name or "Custom Item"

    @property
    def subtotal(self):
        return self.quantity * self.unit_price

    @property
    def profit(self):
        return self.quantity * (self.unit_price - self.unit_cost)

    def __str__(self):
        return f"{self.display_name} × {self.quantity}"


class CustomizationRequest(models.Model):

    customer_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20)
    address = models.TextField(blank=True)

    reference_image = models.ImageField(
        upload_to='customization/',
        blank=True,
        null=True
    )

    description = models.TextField()

    is_contacted = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.customer_name} - Customization Request"
