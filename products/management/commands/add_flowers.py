
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from products.models import Category, Product


class Command(BaseCommand):
    help = "Add nine flowers to Loose Blooms"

    def handle(self, *args, **options):

        try:
            category = Category.objects.get(slug="loose-blooms")
        except Category.DoesNotExist:
            raise CommandError("Loose Blooms category not found!")

        flowers = [
            {
                "name": "White Lily",
                "price": "180",
                "short": "Elegant white lilies with graceful petals, perfect for thoughtful gifts and special occasions.",
                "story": "White Lily brings elegance and calm to every floral arrangement. Its beautiful white petals make it a lovely choice for celebrations, gifting and everyday floral styling."
            },
            {
                "name": "Red Lily",
                "price": "180",
                "short": "Beautiful red lilies that add a bold and elegant touch to floral arrangements.",
                "story": "Red Lily stands out with its rich colour and graceful appearance. Choose it to create expressive floral arrangements or make a thoughtful gift feel extra special."
            },
            {
                "name": "Yellow Rose",
                "price": "130",
                "short": "Bright yellow roses that bring warmth, happiness and a cheerful touch.",
                "story": "Yellow Rose is a lovely way to express friendship, happiness and appreciation. Its sunny colour adds brightness to bouquets, celebrations and everyday moments."
            },
            {
                "name": "White Rose",
                "price": "140",
                "short": "Classic white roses with a soft and graceful appearance.",
                "story": "White Rose represents elegance and simplicity. Its timeless beauty makes it suitable for thoughtful gifts, meaningful occasions and minimal floral arrangements."
            },
            {
                "name": "China Rose",
                "price": "80",
                "short": "Delicate China Roses that add natural charm and colour to your collection.",
                "story": "China Rose adds a delicate floral touch to everyday arrangements and creative floral styling. A charming choice for anyone who appreciates natural beauty."
            },
            {
                "name": "Limu",
                "price": "60",
                "short": "A lovely floral selection for adding variety to your flower collection.",
                "story": "Limu is available as an individual flower product at ALEEN. Add it to your floral selection for gifting, decorating or creating your own arrangements."
            },
            {
                "name": "Gypsum",
                "price": "50",
                "short": "Delicate decorative blooms for a soft finishing touch to flower arrangements.",
                "story": "Gypsum adds a gentle decorative touch to floral styling. Its delicate appearance makes it useful for complementing other flowers and creating balanced arrangements."
            },
            {
                "name": "Tuberose",
                "price": "100",
                "short": "Beautiful Tuberose flowers, appreciated for their elegant appearance and fragrance.",
                "story": "Tuberose is a graceful floral choice known for its distinctive fragrance. It brings an elegant and refreshing touch to special occasions and everyday floral displays."
            },
            {
                "name": "Sunflower",
                "price": "200",
                "short": "Bright sunflowers that bring a cheerful and sunny feeling to any space.",
                "story": "Sunflower is loved for its bright, cheerful appearance. It makes a wonderful choice for gifting, celebrations and adding sunshine to someone's day."
            },
        ]

        added = 0
        skipped = 0

        for flower in flowers:
            product, created = Product.objects.get_or_create(
                category=category,
                name=flower["name"],
                defaults={
                    "pricing_type": "PIECE",
                    "cost_price": Decimal("0"),
                    "selling_price": Decimal(flower["price"]),
                    "stock_qty": 10,
                    "short_description": flower["short"],
                    "story_description": flower["story"],
                    "is_available": True,
                    "is_hero_featured": False,
                }
            )

            if created:
                added += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Added: {product.name}"
                    )
                )
            else:
                skipped += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"Already exists, skipped: {flower['name']}"
                    )
                )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Completed! Added: {added}, Skipped: {skipped}"
            )
        )
