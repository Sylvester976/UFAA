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

    # this is a model for jobseeker to create their account

class JobseekerAccount(models.Model):
    email = models.EmailField(unique=True)
    id_no = models.CharField(max_length=50, unique=True, db_index=True)
    name = models.CharField(max_length=255)

    password = models.CharField(max_length=255)

    account_type = models.IntegerField(default=1)  # 1 = External, 2 = Internal
    session_key = models.CharField(max_length=40, blank=True, null=True)
    verification_token = models.UUIDField(default=uuid.uuid4, editable=False)

    is_active = models.BooleanField(default=True)
    is_verified = models.BooleanField(default=False)

    date_joined = models.DateTimeField(default=timezone.now)
    last_login = models.DateTimeField(null=True, blank=True)

    def set_password(self, raw_password):
        self.password = make_password(raw_password)

    def check_password(self, raw_password):
        return check_password(raw_password, self.password)

    def __str__(self):
        return f"{self.id_no} - {self.name}"


class JobseekerProfile(models.Model):
    user = models.OneToOneField(
        JobseekerAccount,
        on_delete=models.CASCADE,
        related_name="profile"
    )

    first_name = models.CharField(max_length=100)
    second_name = models.CharField(max_length=100)
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=20)
    ethnic_group = models.CharField(max_length=100)
    home_county = models.CharField(max_length=100)
    disability_status = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.user.id_no} Profile"
    
    
class AcademicQualification(models.Model):
    user = models.ForeignKey(
        JobseekerAccount,
        on_delete=models.CASCADE,
        related_name="academic_qualifications"
    )

    level = models.CharField(max_length=100)  # Primary, Secondary, University
    institution = models.CharField(max_length=255, null=True)

    certificate = models.FileField(
        upload_to="academic_certificates/",
        null=True,
        blank=True
    )

    transcript = models.FileField(
        upload_to="academic_transcripts/",
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.user.id_no} - {self.level}"
    
 
class ProfessionalQualification(models.Model):
    user = models.ForeignKey(
        JobseekerAccount,
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
        JobseekerAccount,
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
        JobseekerAccount,
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