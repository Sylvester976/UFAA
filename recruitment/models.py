from django.db import models
from accounts.models import JobseekerAccount

from django.db import models
from django.conf import settings
from django.utils import timezone

from django.utils import timezone
from django.db.models import Avg

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
    
    

class Vacancy(models.Model):

    TYPE_CHOICES = [
        ('external', 'External'),
        ('internal', 'Internal'),
    ]
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('open', 'Open'),
        ('longlisting', 'Longlisting'),
        ('shortlisting', 'Shortlisting'),
        ('interviews', 'Interviews'),
        ('top_three_selected', 'Top Three Selected'),
        ('pending_ceo_approval', 'Pending CEO Approval'),
        ('approved', 'Approved'),
        ('appointed', 'Appointed'),
    ]

    title = models.CharField(max_length=255)
    reference_number = models.CharField(max_length=100, unique=True)
    description = models.TextField()
    advert_pdf = models.FileField(upload_to='media/vacancy_adverts/')

    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='draft')

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    ranking_finalized = models.BooleanField(default=False)

    def is_open(self):
        today = timezone.now().date()
        return (
            self.status == 'open'
            and self.start_date <= today <= self.end_date
        )

    def __str__(self):
        return f"{self.title} ({self.reference_number})"
    
    vacancy_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default='external'
    )

    def auto_close_if_expired(self):
        if self.status == 'open' and self.end_date < timezone.now().date():
            self.status = 'closed'
            self.save()
            


class Application(models.Model):

    STATUS_CHOICES = [
        ('submitted', 'Submitted'),
        ('shortlisted', 'Shortlisted'),
        ('interviewed', 'Interviewed'),
        ('selected_top_three', 'Top Three'),
        ('approved', 'Approved'),
        ('selected', 'Selected'),
        ('not_selected', 'Not Selected'),
    ]

    vacancy = models.ForeignKey(Vacancy, on_delete=models.CASCADE, related_name='applications')
    applicant = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    cv = models.FileField(upload_to='media/cvs/')
    cover_letter = models.TextField()
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='submitted')
    applied_at = models.DateTimeField(auto_now_add=True)

    def average_score(self):
        return self.scores.aggregate(avg=Avg('score'))['avg'] or 0

    def __str__(self):
        return f"{self.applicant} - {self.vacancy}"
    

class PanelAssignment(models.Model):
    vacancy = models.ForeignKey(Vacancy, on_delete=models.CASCADE, related_name='panel_assignments')
    panelist = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('vacancy', 'panelist')
        
class InterviewScore(models.Model):
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name='scores')
    panelist = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    score = models.DecimalField(max_digits=5, decimal_places=2)
    remarks = models.TextField(blank=True)

    class Meta:
        unique_together = ('application', 'panelist')

class TieBreakDecision(models.Model):
    vacancy = models.ForeignKey(Vacancy, on_delete=models.CASCADE)
    selected_application = models.ForeignKey(Application, on_delete=models.CASCADE)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    reason = models.TextField()
    decided_at = models.DateTimeField(auto_now_add=True)
    
class CEODecision(models.Model):
    vacancy = models.ForeignKey(Vacancy, on_delete=models.CASCADE)
    selected_application = models.ForeignKey(Application, on_delete=models.CASCADE)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    is_override = models.BooleanField(default=False)
    reason = models.TextField(blank=True)
    approved_at = models.DateTimeField(auto_now_add=True)
    
class Appointment(models.Model):
    vacancy = models.ForeignKey(Vacancy, on_delete=models.CASCADE)
    application = models.ForeignKey(Application, on_delete=models.CASCADE)
    appointed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    appointed_at = models.DateTimeField(auto_now_add=True)
    appointment_letter = models.FileField(upload_to='media/appointments/', blank=True, null=True)