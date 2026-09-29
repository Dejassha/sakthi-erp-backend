from django.core.management.base import BaseCommand
from django.db import transaction
from api.models import All_User

class Command(BaseCommand):
    help = "Safely converts all unhashed legacy plaintext passwords in All_User database table into PBKDF2 salted hashes without data loss."

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("Starting safe password hashing migration..."))
        
        users = All_User.objects.all()
        updated_count = 0
        skipped_count = 0

        with transaction.atomic():
            for user in users:
                # Check if password is already hashed (pbkdf2_sha256$, bcrypt$, argon2$, etc.)
                if user.password and (
                    user.password.startswith("pbkdf2_sha256$") or
                    user.password.startswith("pbkdf2_sha1$") or
                    user.password.startswith("argon2$") or
                    user.password.startswith("bcrypt$")
                ):
                    skipped_count += 1
                else:
                    # Safely hash raw password without touching any other user data
                    user.set_password(user.password)
                    user.save(update_fields=["password"])
                    updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully completed! {updated_count} user password(s) hashed. {skipped_count} user(s) were already hashed. No user data was lost or modified."
            )
        )
