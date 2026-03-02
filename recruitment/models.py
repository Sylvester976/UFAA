import uuid
from django.db import models
from accounts.models import User
from django.conf import settings
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
#okay
class JobSeekerProfile(models.Model):
    user                = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
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
    disability_other = models.CharField(max_length=255, blank=True, null=True)
    employee_number = models.CharField(max_length=50, blank=True, null=True)
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
    user            = models.ForeignKey(User, on_delete=models.CASCADE, related_name='academic_qualifications')
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
    user          = models.ForeignKey(User, on_delete=models.CASCADE, related_name='documents')
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
        ('ceo_review', 'CEO Review'),
        ('ceo_approved', 'CEO Approved'),
        ('appointed', 'Appointed')
    ]
    ceo_override = models.BooleanField(default=False)
    ceo_override_reason = models.TextField(blank=True, null=True)
    ceo_selected = models.BooleanField(default=False)
    
    vacancy = models.ForeignKey(Vacancy, on_delete=models.CASCADE, related_name='applications')
    applicant = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    cv = models.FileField(upload_to='media/cvs/')
    cover_letter = models.TextField()
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='submitted')
    applied_at = models.DateTimeField(auto_now_add=True)
    interview_locked = models.BooleanField(default=False)
    
    def average_score(self):
        return self.scores.aggregate(avg=Avg('score'))['avg'] or 0

    def __str__(self):
        return f"{self.applicant} - {self.vacancy}"

    class Meta:
        unique_together = ('vacancy', 'applicant')


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

class ProfessionalQualification(models.Model):
    user              = models.ForeignKey(User, on_delete=models.CASCADE,
                                          related_name='professional_qualifications')
    qualification     = models.CharField(max_length=255)          # e.g. CPA, PMP
    awarding_body     = models.CharField(max_length=255)          # institution
    year_obtained     = models.PositiveIntegerField()
    expiry_year       = models.PositiveIntegerField(null=True, blank=True)
    grade             = models.CharField(max_length=100, blank=True)
    cert_number       = models.CharField(max_length=100, blank=True)
    country           = models.CharField(max_length=100, default='Kenya')
    created_at        = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-year_obtained']

class WorkHistory(models.Model):

    EMPLOYMENT_TYPES = [
        ('Full-time',   'Full-time'),
        ('Part-time',   'Part-time'),
        ('Contract',    'Contract'),
        ('Internship',  'Internship'),
        ('Volunteer',   'Volunteer'),
        ('Attachment',  'Attachment'),
    ]

    MONTHS = [
        (1, 'January'),   (2, 'February'),  (3, 'March'),
        (4, 'April'),     (5, 'May'),       (6, 'June'),
        (7, 'July'),      (8, 'August'),    (9, 'September'),
        (10, 'October'),  (11, 'November'), (12, 'December'),
    ]

    user            = models.ForeignKey(User, on_delete=models.CASCADE,
                          related_name='work_history'
                      )
    job_title       = models.CharField(max_length=255)
    company         = models.CharField(max_length=255)
    employment_type = models.CharField(max_length=50, blank=True, choices=EMPLOYMENT_TYPES)
    start_month     = models.PositiveIntegerField()
    start_year      = models.PositiveIntegerField()
    end_month       = models.PositiveIntegerField(null=True, blank=True)
    end_year        = models.PositiveIntegerField(null=True, blank=True)
    is_current      = models.BooleanField(default=False)
    duties          = models.TextField(blank=True)
    exit_reason     = models.CharField(max_length=255, blank=True)
    country         = models.CharField(max_length=100, default='Kenya')
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-start_year', '-start_month']

    def __str__(self):
        return f"{self.job_title} at {self.company}"

    @property
    def start_display(self):
        month_name = dict(self.MONTHS).get(self.start_month, '')
        return f"{month_name} {self.start_year}"

    @property
    def end_display(self):
        if self.is_current:
            return 'Present'
        if self.end_month and self.end_year:
            month_name = dict(self.MONTHS).get(self.end_month, '')
            return f"{month_name} {self.end_year}"
        return '—'

class AdditionalDetail(models.Model):

    AVAILABILITY_CHOICES = [
        ('Immediately',    'Immediately'),
        ('1 Month Notice', '1 Month Notice'),
        ('2 Months Notice','2 Months Notice'),
        ('3 Months Notice','3 Months Notice'),
        ('Not Available',  'Not Available'),
    ]

    user            = models.OneToOneField(User, on_delete=models.CASCADE,
                          related_name='additional_detail'
                      )
    cv              = models.FileField(upload_to='cvs/', null=True, blank=True)
    cover_letter    = models.TextField(blank=True)
    linkedin_url    = models.URLField(max_length=300, blank=True)
    portfolio_url   = models.URLField(max_length=300, blank=True)
    languages       = models.CharField(max_length=500, blank=True)  # comma-separated
    availability    = models.CharField(max_length=50, blank=True,
                          choices=AVAILABILITY_CHOICES)
    expected_salary = models.PositiveIntegerField(null=True, blank=True)
    updated_at      = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Additional Details — {self.user}"

    @property
    def cv_filename(self):
        if self.cv:
            return self.cv.name.split('/')[-1]
        return None

    @property
    def languages_list(self):
        if self.languages:
            return [l.strip() for l in self.languages.split(',') if l.strip()]
        return []