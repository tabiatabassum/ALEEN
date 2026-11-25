
import os

from django.contrib import admin, messages
from django.core.files.base import ContentFile
from django.utils.html import format_html

from .models import (
    HeroSlide,
    BannerAd,
    Review,
    StoreMemory,
    Coupon,
    SiteSettings,
)

from .utils import process_hero_bouquet


@admin.action(description="Remove Background & Uniform Resize (Selected Slides)")
def clean_and_resize_slides(modeladmin, request, queryset):
    success_count = 0

    for slide in queryset:
        if not slide.image:
            continue

        processed_io, status_msg = process_hero_bouquet(slide.image)

        if processed_io:
            base_name = os.path.splitext(
                os.path.basename(slide.image.name)
            )[0].replace('_clean', '')

            new_filename = f"{base_name}_clean.png"

            slide.image.save(
                new_filename,
                ContentFile(processed_io.read()),
                save=False
            )

            super(HeroSlide, slide).save(update_fields=['image'])
            success_count += 1

        else:
            modeladmin.message_user(
                request,
                f"{slide.name}: {status_msg}",
                level=messages.ERROR
            )

    if success_count:
        modeladmin.message_user(
            request,
            f"{success_count}টি ফুলের ব্যাকগ্রাউন্ড রিমুভ ও সাইজ সমান করা হয়েছে!",
            level=messages.SUCCESS
        )


@admin.register(HeroSlide)
class HeroSlideAdmin(admin.ModelAdmin):
    list_display = ('name', 'display_order', 'is_active', 'created_at')
    list_editable = ('display_order', 'is_active')
    list_filter = ('is_active',)
    actions = [clean_and_resize_slides]


@admin.register(BannerAd)
class BannerAdAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'heading',
        'banner_preview',
        'is_active',
        'created_at',
    )

    list_filter = ('is_active',)
    search_fields = ('title', 'heading')
    ordering = ('-created_at', '-id')

    readonly_fields = ('banner_preview', 'created_at')

    fieldsets = (
        ('Banner Information', {
            'fields': ('title', 'image', 'banner_preview')
        }),
        ('Banner Content', {
            'fields': (
                'heading',
                'description',
                'button_text',
                'link',
            )
        }),
        ('Visibility', {
            'fields': ('is_active', 'created_at')
        }),
    )

    @admin.display(description='Image Preview')
    def banner_preview(self, obj):
        if obj and obj.image:
            return format_html(
                '<img src="{}" style="max-width:350px; max-height:160px; object-fit:cover; border-radius:10px;" />',
                obj.image.url
            )

        return "No image uploaded"


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = (
        'shop_name',
        'contact_phone',
        'contact_email',
    )

    fieldsets = (
        ('Website Settings', {
            'fields': (
                'show_visitor_count',
            )
        }),

        ('Shop Information', {
            'fields': (
                'shop_name',
                'shop_address',
                'website_url',
                'contact_phone',
                'contact_email',
            )
        }),

        ('Social Media Links', {
            'fields': (
                'instagram_url',
                'facebook_url',
            )
        }),

        ('Homepage Rose Banner Quote', {
            'fields': (
                'rose_quote',
                'rose_quote_attribution',
            )
        }),

        ('Shipping Settings', {
            'fields': (
                'default_shipping_fee',
            )
        }),

        ('Membership Settings', {
            'fields': (
                'membership_fee',
                'membership_benefits',
                'quick_membership_phone',
            )
        }),
    )


admin.site.register(Review)
admin.site.register(StoreMemory)
admin.site.register(Coupon)
