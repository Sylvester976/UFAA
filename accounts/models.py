# apps/accounts/models.py

import uuid
from django.db import models
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.utils import timezone


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Users must have an email address")

        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superadmin(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_superadmin", True)
        extra_fields.setdefault("is_active", True)

        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    national_id = models.CharField(max_length=20)
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=120)
    last_name = models.CharField(max_length=120)

    role = models.ManyToManyField(
        "roles.Role",
        blank=True,
        related_name="users"
    )
    

    is_active = models.BooleanField(default=True)
    is_superadmin = models.BooleanField(default=False)

    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.email


class External(models.Model):
    user = models.OneToOneField(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="external"
    )

    national_id = models.CharField(max_length=20)
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=20)
    ethnic_group = models.CharField(max_length=100)
    home_county = models.CharField(max_length=100)
    disability_status = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.email}"
    
    
class Internal(models.Model):
    user = models.OneToOneField(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="internal"
    )

    national_id = models.CharField(max_length=20)
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=20)
    ethnic_group = models.CharField(max_length=100)
    home_county = models.CharField(max_length=100)
    disability_status = models.BooleanField(default=False)
    job_group = models.CharField(max_length=50)
    designation = models.CharField(max_length=150)
    date_of_appointment = models.DateField()

    def __str__(self):
        return f"{self.user.email} - {self.designation}"