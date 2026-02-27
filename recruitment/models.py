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