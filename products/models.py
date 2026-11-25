
from django.db import models
from django.utils.text import slugify
from django.core.files.base import ContentFile
from decimal import Decimal
from PIL import Image, ImageOps, ImageFilter
from io import BytesIO
import os


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

    image = models.ImageField(
        upload_to='categories/',
        blank=True,
        null=True
    )

    display_order = models.PositiveIntegerField(default=0)

    short_description = models.CharField(
        max_length=250,
        blank=True,
        help_text="Homepage category card-এ ছোট description দেখাবে"
    )

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

    IMAGE_WIDTH = 1200
    IMAGE_HEIGHT = 960

    PRICING_TYPE_CHOICES = [
        ('PIECE', 'Per Flower / Per Piece'),
        ('BAG', 'Per Bag'),
        ('BOUQUET', 'Per Bouquet'),
    ]

    OCCASION_CHOICES = [
        ('birthday', 'Birthday'),
        ('anniversary', 'Anniversary'),
        ('valentines_day', "Valentine's Day"),
        ('congratulations', 'Congratulations'),
        ('thank_you', 'Thank You'),
        ('get_well_soon', 'Get Well Soon'),
        ('just_because', 'Just Because'),
    ]

    RECIPIENT_CHOICES = [
        ('mother', 'Mother'),
        ('father', 'Father'),
        ('sister', 'Sister'),
        ('brother', 'Brother'),
        ('friend', 'Friend'),
        ('partner', 'Partner'),
        ('colleague', 'Colleague'),
    ]

    BUDGET_CHOICES = [
        ('under_500', 'Under ৳500'),
        ('500_1000', '৳500 – ৳1,000'),
        ('1000_2000', '৳1,000 – ৳2,000'),
        ('2000_5000', '৳2,000 – ৳5,000'),
        ('5000_plus', '৳5,000+'),
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
        help_text="কেনা খরচ / প্রতি ইউনিটের খরচ"
    )

    selling_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Regular Price",
        help_text="প্রতি ফুল, bag বা bouquet-এর আসল দাম"
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

    sentimental_description = models.TextField(
        blank=True,
        help_text="এই ফুলটি কী অনুভূতি বা আবেগ প্রকাশ করে"
    )

    flower_care = models.TextField(
        blank=True,
        help_text="Water, sunlight, temperature, freshness tips ও common care mistakes একসঙ্গে লিখুন।"
    )

    # Gift Finder Information
    gift_occasions = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Suitable Occasions",
        help_text="এই Product-এর জন্য উপযুক্ত Occasion নির্বাচন করুন।"
    )

    gift_recipients = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Suitable Recipients",
        help_text="এই Product কাদের উপহার দেওয়া যায় তা নির্বাচন করুন।"
    )

    gift_budgets = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Suitable Budget",
        help_text="এই Product-এর জন্য উপযুক্ত Budget নির্বাচন করুন।"
    )

    is_hero_featured = models.BooleanField(
        default=False,
        help_text="Homepage featured section-এ দেখাবেন?"
    )

    is_available = models.BooleanField(default=True)

    sales_count = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    def process_product_image(self):
        if not self.image:
            return

        # Open image and correct orientation
        source = Image.open(self.image)
        source = ImageOps.exif_transpose(source)

        # Handle transparent images safely
        if source.mode in ('RGBA', 'LA') or 'transparency' in source.info:
            rgba = source.convert('RGBA')

            base = Image.new(
                'RGBA',
                rgba.size,
                (250, 247, 242, 255)
            )

            base.alpha_composite(rgba)
            source = base.convert('RGB')
        else:
            source = source.convert('RGB')

        target_size = (
            self.IMAGE_WIDTH,
            self.IMAGE_HEIGHT
        )

        # Loose Blooms: original flower with blurred background
        if self.category.name == 'Loose Blooms':

            background = ImageOps.fit(
                source,
                target_size,
                method=Image.Resampling.LANCZOS
            )

            background = background.filter(
                ImageFilter.GaussianBlur(radius=22)
            )

            foreground = source.copy()

            foreground.thumbnail(
                target_size,
                Image.Resampling.LANCZOS
            )

            x = (self.IMAGE_WIDTH - foreground.width) // 2
            y = (self.IMAGE_HEIGHT - foreground.height) // 2

            background.paste(
                foreground,
                (x, y)
            )

            final_image = background

        else:
            # Flower Bags, Flower Bouquets and Artificial Blooms:
            # Resize the complete original image without cropping
            resized_image = ImageOps.contain(
                source,
                target_size,
                method=Image.Resampling.LANCZOS
            )

            # Create a 1200 x 960 background
            background = Image.new(
                'RGB',
                target_size,
                (250, 247, 242)
            )

            # Center the complete resized image
            x = (self.IMAGE_WIDTH - resized_image.width) // 2
            y = (self.IMAGE_HEIGHT - resized_image.height) // 2

            background.paste(
                resized_image,
                (x, y)
            )

            final_image = background

        # Save optimized WebP image
        output = BytesIO()

        final_image.save(
            output,
            format='WEBP',
            quality=85,
            method=6
        )

        original_name = os.path.splitext(
            os.path.basename(self.image.name)
        )[0]

        new_name = f"{original_name}.webp"

        self.image.save(
            new_name,
            ContentFile(output.getvalue()),
            save=False
        )

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
        if self.pricing_type == 'BAG':
            return 'per bag'

        if self.pricing_type == 'BOUQUET':
            return 'per bouquet'

        if self.category.name == 'Loose Blooms':
            return 'per flower'

        return 'per piece'

    @property
    def profit_per_unit(self):
        return self.current_price - self.cost_price

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)

        if self.image and not self.image._committed:
            self.process_product_image()

        super().save(*args, **kwargs)

    def __str__(self):
        return self.name
