import uuid
from django.db import models
from accounts.models import JobseekerAccount


class Gender(models.Model):
    name = models.CharField(max_length=50, unique=True)

    class Meta:
        verbose_name        = 'Gender'
        verbose_name_plural = 'Genders'
        ordering            = ['name']

    def __str__(self):
        return self.name

class EthnicGroup(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        verbose_name        = 'Ethnic Group'
        verbose_name_plural = 'Ethnic Groups'
        ordering            = ['name']

    def __str__(self):
        return self.name

class County(models.Model):
    name = models.CharField(max_length=100, unique=True)
    code = models.IntegerField(unique=True)

    class Meta:
        verbose_name        = 'County'
        verbose_name_plural = 'Counties'
        ordering            = ['code']

    def __str__(self):
        return self.name


class Constituency(models.Model):
    name   = models.CharField(max_length=100)
    county = models.ForeignKey(County, on_delete=models.CASCADE, related_name='constituencies')

    class Meta:
        verbose_name        = 'Constituency'
        verbose_name_plural = 'Constituencies'
        ordering            = ['name']

    def __str__(self):
        return f'{self.name} — {self.county.name}'


class SubCounty(models.Model):
    name   = models.CharField(max_length=100)
    county = models.ForeignKey(County, on_delete=models.CASCADE, related_name='sub_counties')

    class Meta:
        verbose_name        = 'Sub County'
        verbose_name_plural = 'Sub Counties'
        ordering            = ['name']

    def __str__(self):
        return f'{self.name} — {self.county.name}'


class Ward(models.Model):
    name         = models.CharField(max_length=100)
    constituency = models.ForeignKey(Constituency, on_delete=models.CASCADE, related_name='wards')

    class Meta:
        verbose_name        = 'Ward'
        verbose_name_plural = 'Wards'
        ordering            = ['name']

    def __str__(self):
        return f'{self.name} — {self.constituency.name}'

class JobSeekerProfile(models.Model):
    user                = models.OneToOneField(JobseekerAccount, on_delete=models.CASCADE, related_name='profile')
    salutation          = models.CharField(max_length=50, blank=True, null=True)
    surname             = models.CharField(max_length=255, blank=True, null=True)
    first_name          = models.CharField(max_length=255, blank=True, null=True)
    second_name         = models.CharField(max_length=255, blank=True, null=True)
    email               = models.EmailField(blank=True, null=True)
    id_no               = models.CharField(max_length=20, blank=True, null=True)
    date_of_birth       = models.DateField(blank=True, null=True)
    gender              = models.ForeignKey(Gender, on_delete=models.SET_NULL, null=True, blank=True)
    ethnic_group        = models.ForeignKey(EthnicGroup, on_delete=models.SET_NULL, null=True, blank=True)
    home_county         = models.ForeignKey(County, on_delete=models.SET_NULL, null=True, blank=True)
    constituency        = models.ForeignKey(Constituency, on_delete=models.SET_NULL, null=True, blank=True)
    sub_county          = models.ForeignKey(SubCounty, on_delete=models.SET_NULL, null=True, blank=True)
    ward                = models.ForeignKey(Ward, on_delete=models.SET_NULL, null=True, blank=True)
    disability_status   = models.CharField(max_length=50, blank=True, null=True)
    date_created        = models.DateTimeField(auto_now_add=True)
    date_updated        = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Job Seeker Profile'
        verbose_name_plural = 'Job Seeker Profiles'

    def __str__(self):
        return f'{self.user.name} — Profile'

class EducationLevel(models.Model):
    name                = models.CharField(max_length=100, unique=True)
    rank                = models.IntegerField(unique=True)  # 1 = highest, 8 = lowest
    is_higher_education = models.BooleanField(default=False)
    is_foreign          = models.BooleanField(default=False)

    class Meta:
        verbose_name        = 'Education Level'
        verbose_name_plural = 'Education Levels'
        ordering            = ['rank']

    def __str__(self):
        return self.name


class AcademicQualification(models.Model):
    user            = models.ForeignKey(JobseekerAccount, on_delete=models.CASCADE, related_name='academic_qualifications')
    education_level = models.ForeignKey(EducationLevel, on_delete=models.PROTECT)
    institution     = models.CharField(max_length=255)
    field_of_study  = models.CharField(max_length=255, blank=True, null=True)
    country         = models.CharField(max_length=100, default='Kenya')
    year_completed  = models.IntegerField()
    grade           = models.CharField(max_length=100, blank=True, null=True)
    cert_number     = models.CharField(max_length=100, blank=True, null=True)
    date_added      = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Academic Qualification'
        verbose_name_plural = 'Academic Qualifications'
        ordering            = ['education_level__rank']

    def __str__(self):
        return f'{self.user.name} — {self.education_level.name} — {self.institution}'


class DocumentType(models.Model):
    name        = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name        = 'Document Type'
        verbose_name_plural = 'Document Types'
        ordering            = ['name']

    def __str__(self):
        return self.name


class Document(models.Model):
    user          = models.ForeignKey(JobseekerAccount, on_delete=models.CASCADE, related_name='documents')
    profile       = models.ForeignKey(JobSeekerProfile, on_delete=models.CASCADE, related_name='documents', null=True, blank=True)
    document_type = models.ForeignKey(DocumentType, on_delete=models.PROTECT)
    file          = models.FileField(upload_to='documents/%Y/%m/')
    unique_ref    = models.CharField(max_length=100, unique=True, editable=False)
    uploaded_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Document'
        verbose_name_plural = 'Documents'
        ordering            = ['-uploaded_at']

    def save(self, *args, **kwargs):
        if not self.unique_ref:
            # Format: UFAA-USERID-DOCTYPE-UUID
            self.unique_ref = f'UFAA-{self.user_id}-{self.document_type_id}-{uuid.uuid4().hex[:8].upper()}'
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.unique_ref} — {self.document_type.name}'