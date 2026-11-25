
from django.db import models
from django.utils.text import slugify
from decimal import Decimal


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True, blank=True)
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='subcategories',
        help_text="সাব-ক্যাটাগরি হলে মেইন ক্যাটাগরি সিলেক্ট করুন।"
    )
    image = models.ImageField(upload_to='categories/', blank=True, null=True)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ['display_order', 'name']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        if self.parent:
            return f"{self.parent.name} → {self.name}"
        return self.name


class Product(models.Model):

    PRICING_TYPE_CHOICES = [
        ('PIECE', 'Per Flower / Per Piece'),
        ('BOUQUET', 'Per Bouquet'),
    ]

    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name='products'
    )

    name = models.CharField(max_length=150)
    slug = models.SlugField(unique=True, blank=True)

    image = models.ImageField(
        upload_to='products/',
        blank=True,
        null=True
    )

    pricing_type = models.CharField(
        max_length=10,
        choices=PRICING_TYPE_CHOICES,
        default='PIECE',
        verbose_name="Pricing Type"
    )

    cost_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="কেনা খরচ / প্রতি ফুলের খরচ"
    )

    selling_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Regular Price",
        help_text="প্রতি ফুল বা প্রতি bouquet-এর আসল দাম"
    )

    discount_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name="Discount Price",
        help_text="Discount price না থাকলে খালি রাখুন"
    )

    stock_qty = models.PositiveIntegerField(default=0)

    short_description = models.TextField(blank=True)

    story_description = models.TextField(
        blank=True,
        help_text="Product details page-এ দেখাবে"
    )

    is_hero_featured = models.BooleanField(
        default=False,
        help_text="Homepage featured section-এ দেখাবেন?"
    )

    is_available = models.BooleanField(default=True)

    sales_count = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def is_in_stock(self):
        return self.stock_qty > 0 and self.is_available

    @property
    def has_discount(self):
        return bool(
            self.discount_price is not None
            and self.discount_price < self.selling_price
        )

    @property
    def current_price(self):
        if self.has_discount:
            return self.discount_price
        return self.selling_price

    @property
    def discount_percentage(self):
        if self.has_discount and self.selling_price > 0:
            discount = (
                (self.selling_price - self.discount_price)
                / self.selling_price
            ) * Decimal('100')
            return int(discount)
        return 0

    @property
    def pricing_unit_label(self):
        if self.pricing_type == 'PIECE':
            return 'per flower'
        return 'per bouquet'

    @property
    def profit_per_unit(self):
        return self.current_price - self.cost_price

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name
