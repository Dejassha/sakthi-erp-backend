from django.core.management.base import BaseCommand
from seed_inventory import seed_inventory_data


class Command(BaseCommand):
    help = "Seeds comprehensive test entries for inventory parts, history ledger, usages, and requisitions."

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Running inventory seed command..."))
        seed_inventory_data()
        self.stdout.write(self.style.SUCCESS("Inventory seeding completed successfully!"))
