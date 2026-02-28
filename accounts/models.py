# apps/accounts/models.py

import uuid
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.hashers import make_password, check_password
from django.db import models
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


# Single user model for internal and external users
class User(AbstractBaseUser):
    USER_TYPE_CHOICES = (
        (1, "external"),  # Jobseeker
        (2, "internal"),  # Staff
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=120, blank=True)
    last_name = models.CharField(max_length=120, blank=True)

    # Optional: only for internal users
    national_id = models.CharField(max_length=20, blank=True, null=True)
    role = models.ManyToManyField("roles.Role", blank=True, related_name="users")

    # Jobseeker-specific fields
    id_no = models.CharField(max_length=50, unique=True, db_index=True, blank=True, null=True)
    full_name = models.CharField(max_length=255, blank=True, null=True)
    session_key = models.CharField(max_length=40, blank=True, null=True)
    verification_token = models.UUIDField(default=uuid.uuid4, editable=False)
    is_verified = models.BooleanField(default=False)

    user_type = models.PositiveSmallIntegerField(choices=USER_TYPE_CHOICES, default=1)

    is_active = models.BooleanField(default=True)
    is_superadmin = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    last_login = models.DateTimeField(null=True, blank=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.email

    @property
    def is_internal(self):
        return self.user_type == 2

    @property
    def is_external(self):
        return self.user_type == 1
    
    
    def set_password(self, raw_password):
        self.password = make_password(raw_password)

    def check_password(self, raw_password):
        return check_password(raw_password, self.password)

    
 
class ProfessionalQualification(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="professional_qualifications"
    )

    institution = models.CharField(max_length=255)
    course = models.CharField(max_length=255)
    completion_date = models.DateField()
    grade = models.CharField(max_length=50)

    certificate = models.FileField(
        upload_to="professional_certificates/",
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.user.id_no} - {self.course}"
       

class WorkHistory(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="work_history"
    )

    company = models.CharField(max_length=255)
    job_title = models.CharField(max_length=255)
    duties = models.TextField()

    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)

    is_current = models.BooleanField(default=False)

    exit_reason = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.user.id_no} - {self.company}"
   

class AdditionalDetail(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="additional_detail"
    )

    cover_letter = models.TextField(null=True, blank=True)

    cv = models.FileField(
        upload_to="cv_uploads/",
        null=True,
        blank=True
    )

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.id_no} Additional Details"