from django.db import models
from django.utils import timezone
from datetime import date, timedelta
from django.contrib.auth.hashers import make_password, check_password as django_check_password

# Role Ba
class Role(models.Model):
    name = models.CharField(max_length=40)

    def __str__(self):
        return self.name


# Role Based Users
class All_User(models.Model):
    username = models.CharField(max_length=30)
    email = models.EmailField(max_length=100)
    password = models.CharField(max_length=255)   
    role = models.ManyToManyField(Role, blank=True)
    isAdmin = models.BooleanField(default=False)
    has_user_management = models.BooleanField(default=False)

    def set_password(self, raw_password):
        self.password = make_password(raw_password)

    def check_password(self, raw_password):
        if django_check_password(raw_password, self.password):
            return True
        if self.password == raw_password:
            # Upgrade legacy plaintext password automatically
            self.set_password(raw_password)
            self.save(update_fields=["password"])
            return True
        return False

    def __str__(self):
        return self.username

    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False


# Admin Role
class Admin(models.Model):
    user = models.OneToOneField(
        All_User, on_delete=models.CASCADE, blank=True, null=True
    )

    def save(self, *args, **kwargs):
        all_role = Role.objects.all()
        self.user.isAdmin = True
        self.user.save()
        self.user.role.set(all_role)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.username} - {self.id}"


