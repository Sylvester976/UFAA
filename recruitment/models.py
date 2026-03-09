import uuid

from django.conf import settings
from django.db import models
from django.db.models import Avg
from django.utils import timezone

from accounts.models import JobseekerAccount


class Gender(models.Model):
    name = models.CharField(max_length=50, unique=True)

    class Meta:
        verbose_name = 'Gender'
        verbose_name_plural = 'Genders'
        ordering = ['name']

    def __str__(self):
        return self.name


class EthnicGroup(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        verbose_name = 'Ethnic Group'
        verbose_name_plural = 'Ethnic Groups'
        ordering = ['name']

    def __str__(self):
        return self.name


class County(models.Model):
    name = models.CharField(max_length=100, unique=True)
    code = models.IntegerField(unique=True)

    class Meta:
        verbose_name = 'County'
        verbose_name_plural = 'Counties'
        ordering = ['code']

    def __str__(self):
        return self.name


class Constituency(models.Model):
    name = models.CharField(max_length=100)
    county = models.ForeignKey(County, on_delete=models.CASCADE, related_name='constituencies')

    class Meta:
        verbose_name = 'Constituency'
        verbose_name_plural = 'Constituencies'
        ordering = ['name']

    def __str__(self):
        return f'{self.name} — {self.county.name}'


class SubCounty(models.Model):
    name = models.CharField(max_length=100)
    county = models.ForeignKey(County, on_delete=models.CASCADE, related_name='sub_counties')

    class Meta:
        verbose_name = 'Sub County'
        verbose_name_plural = 'Sub Counties'
        ordering = ['name']

    def __str__(self):
        return f'{self.name} — {self.county.name}'


class Ward(models.Model):
    name = models.CharField(max_length=100)
    constituency = models.ForeignKey(Constituency, on_delete=models.CASCADE, related_name='wards')

    class Meta:
        verbose_name = 'Ward'
        verbose_name_plural = 'Wards'
        ordering = ['name']

    def __str__(self):
        return f'{self.name} — {self.constituency.name}'


# okay
class JobSeekerProfile(models.Model):
    user = models.OneToOneField(JobseekerAccount, on_delete=models.CASCADE, related_name='profile')
    salutation = models.CharField(max_length=50, blank=True, null=True)
    surname = models.CharField(max_length=255, blank=True, null=True)
    first_name = models.CharField(max_length=255, blank=True, null=True)
    second_name = models.CharField(max_length=255, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    id_no = models.CharField(max_length=20, blank=True, null=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    gender = models.ForeignKey(Gender, on_delete=models.SET_NULL, null=True, blank=True)
    ethnic_group = models.ForeignKey(EthnicGroup, on_delete=models.SET_NULL, null=True, blank=True)
    home_county = models.ForeignKey(County, on_delete=models.SET_NULL, null=True, blank=True)
    constituency = models.ForeignKey(Constituency, on_delete=models.SET_NULL, null=True, blank=True)
    sub_county = models.ForeignKey(SubCounty, on_delete=models.SET_NULL, null=True, blank=True)
    ward = models.ForeignKey(Ward, on_delete=models.SET_NULL, null=True, blank=True)
    disability_status = models.CharField(max_length=50, blank=True, null=True)
    disability_other = models.CharField(max_length=255, blank=True, null=True)
    disability_no = models.CharField(max_length=50, blank=True, null=True)
    employee_number = models.CharField(max_length=50, blank=True, null=True)
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Job Seeker Profile'
        verbose_name_plural = 'Job Seeker Profiles'

    def __str__(self):
        return f'{self.user.name} — Profile'


class EducationLevel(models.Model):
    name = models.CharField(max_length=100, unique=True)
    rank = models.IntegerField(unique=True)  # 1 = highest, 8 = lowest
    is_higher_education = models.BooleanField(default=False)
    is_foreign = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Education Level'
        verbose_name_plural = 'Education Levels'
        ordering = ['rank']

    def __str__(self):
        return self.name


class AcademicQualification(models.Model):
    user = models.ForeignKey(JobseekerAccount, on_delete=models.CASCADE, related_name='academic_qualifications')
    education_level = models.ForeignKey(EducationLevel, on_delete=models.PROTECT)
    institution = models.CharField(max_length=255)
    field_of_study = models.CharField(max_length=255, blank=True, null=True)
    country = models.CharField(max_length=100, default='Kenya')
    year_completed = models.IntegerField()
    grade = models.CharField(max_length=100, blank=True, null=True)
    cert_number = models.CharField(max_length=100, blank=True, null=True)
    date_added = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Academic Qualification'
        verbose_name_plural = 'Academic Qualifications'
        ordering = ['education_level__rank']

    def __str__(self):
        return f'{self.user.name} — {self.education_level.name} — {self.institution}'


class DocumentType(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = 'Document Type'
        verbose_name_plural = 'Document Types'
        ordering = ['name']

    def __str__(self):
        return self.name


class Document(models.Model):
    user = models.ForeignKey(JobseekerAccount, on_delete=models.CASCADE, related_name='documents')
    profile = models.ForeignKey(JobSeekerProfile, on_delete=models.CASCADE, related_name='documents', null=True,
                                blank=True)
    document_type = models.ForeignKey(DocumentType, on_delete=models.PROTECT)
    file = models.FileField(upload_to='documents/%Y/%m/')
    unique_ref = models.CharField(max_length=100, unique=True, editable=False)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Document'
        verbose_name_plural = 'Documents'
        ordering = ['-uploaded_at']

    def save(self, *args, **kwargs):
        if not self.unique_ref:
            # Format: UFAA-USERID-DOCTYPE-UUID
            self.unique_ref = f'UFAA-{self.user_id}-{self.document_type_id}-{uuid.uuid4().hex[:8].upper()}'
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.unique_ref} — {self.document_type.name}'


class InterviewTemplate(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
 

class Vacancy(models.Model):
    TYPE_CHOICES = [
        ('external', 'External'),
        ('internal', 'Internal'),
    ]

    GRADE_CHOICES = [
        ('10-5', 'Grade 10-5'),
        ('4-1',  'Grade 4-1'),
    ]

    STATUS_CHOICES = [
        ('draft',                'Draft'),
        ('open',                 'Open'),
        ('closed',               'Closed'),               # ← ADDED: HR closes after deadline
        ('longlisting',          'Longlisting'),
        ('committee_stage',      'Committee Appointed'),
        ('shortlisting',         'Shortlisting Stage'),
        ('interviews',           'Interviews'),
        ('top_three_selected',   'Top Three Selected'),
        ('pending_ceo_approval', 'Pending CEO Approval'),
        ('approved',             'Approved'),
        ('appointed',            'Appointed'),
    ]
    interview_template = models.ForeignKey(
        InterviewTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vacancies"
    )
    title            = models.CharField(max_length=255)
    reference_number = models.CharField(max_length=100, unique=True)
    description      = models.TextField()

    # ↓ CHANGED: null=True, blank=True — PDF is optional at creation
    advert_pdf = models.FileField(
        upload_to='vacancy_adverts/',
        null=True,
        blank=True,
    )

    grade_category = models.CharField(
        max_length=20,  # increased from 10
        choices=GRADE_CHOICES,
        default='4-1',
    )
    vacancy_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default='external',
    )
    status = models.CharField(
        max_length=50,
        choices=STATUS_CHOICES,
        default='draft',
    )
    screening_criteria = models.JSONField(default=dict, blank=True)

    start_date = models.DateField()
    end_date   = models.DateField()

    created_by       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at       = models.DateTimeField(auto_now_add=True)
    ranking_finalized = models.BooleanField(default=False)

    def is_open(self):
        today = timezone.now().date()
        return (
            self.status == 'open'
            and self.start_date is not None
            and self.end_date is not None
            and self.start_date <= today <= self.end_date
        )

    def auto_close_if_expired(self):
        """
        Called by a scheduled task / management command.
        Moves open vacancies past their end_date to 'closed'.
        """
        if self.status == 'open' and self.end_date < timezone.now().date():
            self.status = 'closed'   # ← now valid — 'closed' is in STATUS_CHOICES
            self.save()

    def move_to(self, new_status):
        """
        Enforces the recruitment workflow progression.
        Returns True if the transition was applied, False otherwise.
        """
        allowed = {
            'draft':                ['open'],
            'open':                 ['closed'],             # HR closes vacancy
            'closed':               ['longlisting'],        # ← NEW: closed → longlisting
            'longlisting':          ['committee_stage'],    # ← FIXED: was jumping to shortlisting
            'committee_stage':      ['shortlisting'],
            'shortlisting':         ['interviews'],
            'interviews':           ['top_three_selected'],
            'top_three_selected':   ['pending_ceo_approval'],
            'pending_ceo_approval': ['approved'],
            'approved':             ['appointed'],
        }

        if new_status in allowed.get(self.status, []):
            self.status = new_status
            self.save()
            return True
        return False

    def __str__(self):
        return f"{self.title} ({self.reference_number})"


class Application(models.Model):
    STATUS_CHOICES = [
        ('submitted', 'Submitted'),
        ('shortlisted', 'Shortlisted'),
        ('interviewed', 'Interviewed'),

        # Grade 10–5 specific
        ('selected_top_five', 'Selected Top Five'),
        ('board_review', 'Board Review'),

        # Shared
        ('selected_top_three', 'Selected Top Three'),
        ('ceo_review', 'CEO Review'),
        ('ceo_approved', 'CEO Approved'),

        ('hr_appoints', 'HR Appoints'),
        ('appointed', 'Appointed'),

        ('not_selected', 'Not Selected'),
    ]
    ceo_override = models.BooleanField(default=False)
    ceo_override_reason = models.TextField(blank=True, null=True)
    ceo_selected = models.BooleanField(default=False)

    vacancy = models.ForeignKey(Vacancy, on_delete=models.CASCADE, related_name='applications')
    applicant = models.ForeignKey(JobseekerAccount, on_delete=models.CASCADE, related_name='applications')
    cv = models.FileField(upload_to='cvs/')
    cover_letter = models.TextField()
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='submitted')
    applied_at = models.DateTimeField(auto_now_add=True)
    interview_locked = models.BooleanField(default=False)
    profile_snapshot = models.JSONField(null=True, blank=True)

    def average_score(self):
        return self.scores.aggregate(avg=Avg('score'))['avg'] or 0

    def __str__(self):
        return f"{self.applicant} - {self.vacancy}"

    class Meta:
        unique_together = ('vacancy', 'applicant')
        
    def move_to(self, new_status):
        allowed_transitions = {
            'submitted': ['shortlisted', 'not_selected'],
            'shortlisted': ['interviewed', 'not_selected'],
            'interviewed': ['selected_top_five', 'selected_top_three', 'not_selected'],

            # Grade 10–5 path
            'selected_top_five': ['ceo_review'],
            'ceo_review': ['selected_top_three', 'ceo_approved'],
            'selected_top_three': ['board_review', 'ceo_approved'],
            'board_review': ['hr_appoints'],

            # Grade 4–1 path
            'ceo_approved': ['hr_appoints'],

            'hr_appoints': ['appointed'],
        }

        if new_status in allowed_transitions.get(self.status, []):
            self.status = new_status
            self.save()
            return True

        return False


class PanelAssignment(models.Model):

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('declined', 'Declined'),
    ]

    COMMITTEE_TYPES = [
        ('shortlisting', 'Shortlisting'),
        ('interview', 'Interview'),
    ]

    vacancy = models.ForeignKey(
        Vacancy,
        on_delete=models.CASCADE,
        related_name='panel_assignments'
    )

    panelist = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )

    committee_type = models.CharField(
        max_length=30,
        choices=COMMITTEE_TYPES,
        null=True,
        blank=True
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )

    decline_reason = models.TextField(blank=True, null=True)

    signed_decline_document = models.FileField(
        upload_to="panel_declines/",
        null=True,
        blank=True
    )

    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('vacancy', 'panelist', 'committee_type')
    

class PanelistReport(models.Model):

    vacancy = models.ForeignKey(
        Vacancy,
        on_delete=models.CASCADE,
        related_name="panel_reports"
    )

    panelist = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )

    assignment = models.ForeignKey(
        PanelAssignment,
        on_delete=models.CASCADE, blank=True, null=True
    )

    candidates_interviewed = models.IntegerField(default=0)

    report_summary = models.TextField()

    recommendations = models.TextField(blank=True)

    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("vacancy", "panelist")


class ShortlistVote(models.Model):

    vacancy = models.ForeignKey(
        Vacancy,
        on_delete=models.CASCADE,
        related_name='shortlist_votes'
    )

    committee_member = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )

    application = models.ForeignKey(
        Application,
        on_delete=models.CASCADE,
        related_name='shortlist_votes'
    )

    voted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('vacancy', 'committee_member', 'application')

class InterviewScore(models.Model):
    application = models.ForeignKey(
        Application,
        on_delete=models.CASCADE,
        related_name="scores"
    )

    panelist = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )

    template = models.ForeignKey(
        InterviewTemplate,
        on_delete=models.PROTECT,  blank=True, null=True
    )

    total_score = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=0
    )

    remarks = models.TextField(blank=True)

    submitted_at = models.DateTimeField(auto_now_add=True, blank=True, null=True)

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
    appointment_letter = models.FileField(upload_to='appointments/', blank=True, null=True)


class ProfessionalQualification(models.Model):
    user = models.ForeignKey(JobseekerAccount, on_delete=models.CASCADE,
                             related_name='professional_qualifications')
    qualification = models.CharField(max_length=255)  # e.g. CPA, PMP
    awarding_body = models.CharField(max_length=255)  # institution
    year_obtained = models.PositiveIntegerField()
    expiry_year = models.PositiveIntegerField(null=True, blank=True)
    grade = models.CharField(max_length=100, blank=True)
    cert_number = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, default='Kenya')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-year_obtained']


class WorkHistory(models.Model):
    EMPLOYMENT_TYPES = [
        ('Full-time', 'Full-time'),
        ('Part-time', 'Part-time'),
        ('Contract', 'Contract'),
        ('Internship', 'Internship'),
        ('Volunteer', 'Volunteer'),
        ('Attachment', 'Attachment'),
    ]

    MONTHS = [
        (1, 'January'), (2, 'February'), (3, 'March'),
        (4, 'April'), (5, 'May'), (6, 'June'),
        (7, 'July'), (8, 'August'), (9, 'September'),
        (10, 'October'), (11, 'November'), (12, 'December'),
    ]

    user = models.ForeignKey(JobseekerAccount, on_delete=models.CASCADE,
                             related_name='work_history'
                             )
    job_title = models.CharField(max_length=255)
    company = models.CharField(max_length=255)
    employment_type = models.CharField(max_length=50, blank=True, choices=EMPLOYMENT_TYPES)
    start_month = models.PositiveIntegerField()
    start_year = models.PositiveIntegerField()
    end_month = models.PositiveIntegerField(null=True, blank=True)
    end_year = models.PositiveIntegerField(null=True, blank=True)
    is_current = models.BooleanField(default=False)
    duties = models.TextField(blank=True)
    exit_reason = models.CharField(max_length=255, blank=True)
    country = models.CharField(max_length=100, default='Kenya')
    created_at = models.DateTimeField(auto_now_add=True)

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
        ('Immediately', 'Immediately'),
        ('1 Week Notice', '1 Week Notice'),
        ('2 Weeks Notice', '2 Weeks Notice'),
        ('3 Weeks Notice', '3 Weeks Notice'),
        ('1 Month Notice', '1 Month Notice'),
        ('2 Months Notice', '2 Months Notice'),
        ('3 Months Notice', '3 Months Notice'),
        ('Not Available', 'Not Available'),
    ]

    user             = models.OneToOneField(
                           JobseekerAccount, on_delete=models.CASCADE,
                           related_name='additional_detail'
                       )
    cv               = models.FileField(upload_to='cvs/', null=True, blank=True)
    cover_letter     = models.FileField(upload_to='cover_letters/', null=True, blank=True)  # changed from TextField
    linkedin_url     = models.URLField(max_length=300, blank=True)
    portfolio_url    = models.URLField(max_length=300, blank=True)
    languages        = models.CharField(max_length=500, blank=True)
    availability     = models.CharField(max_length=50, blank=True, choices=AVAILABILITY_CHOICES)
    expected_salary  = models.PositiveIntegerField(null=True, blank=True)
    updated_at       = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Additional Details — {self.user}"

    @property
    def cv_filename(self):
        return self.cv.name.split('/')[-1] if self.cv else None

    @property
    def cover_letter_filename(self):
        return self.cover_letter.name.split('/')[-1] if self.cover_letter else None

    @property
    def languages_list(self):
        if self.languages:
            return [l.strip() for l in self.languages.split(',') if l.strip()]
        return []


class ProfessionalBodyMembership(models.Model):
    user = models.ForeignKey(
        'accounts.JobseekerAccount',
        on_delete=models.CASCADE,
        related_name='body_memberships'
    )
    body_name = models.CharField(max_length=255)  # e.g. ICPAK, LSK, KISM
    membership_no = models.CharField(max_length=100)
    year_joined = models.PositiveIntegerField()
    expiry_year = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-year_joined']

    def __str__(self):
        return f"{self.body_name} — {self.user}"

# ── In recruitment/models.py ──────────────────────────────────
# Add after ProfessionalBodyMembership model

class Referee(models.Model):

    PERIOD_CHOICES = [
        ('Less than 1 year', 'Less than 1 year'),
        ('1 - 2 years',      '1 - 2 years'),
        ('3 - 5 years',      '3 - 5 years'),
        ('6 - 10 years',     '6 - 10 years'),
        ('Over 10 years',    'Over 10 years'),
    ]

    user         = models.ForeignKey(
                       'accounts.JobseekerAccount',
                       on_delete=models.CASCADE,
                       related_name='referees'
                   )
    referee_no   = models.PositiveIntegerField()   # 1 or 2
    name         = models.CharField(max_length=255)
    occupation   = models.CharField(max_length=255)
    mobile       = models.CharField(max_length=20)
    email        = models.EmailField()
    period_known = models.CharField(max_length=50, choices=PERIOD_CHOICES)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        ordering          = ['referee_no']
        unique_together   = ('user', 'referee_no')   # one referee 1, one referee 2 per user

    def __str__(self):
        return f"Referee {self.referee_no} — {self.name} ({self.user})"

class JobApplicationStatus(models.Model):
    code        = models.CharField(max_length=50, unique=True)
    name        = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    order       = models.PositiveIntegerField(default=0)
    is_terminal = models.BooleanField(default=False)   # no further changes after this

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.name


class JobApplication(models.Model):
    user = models.ForeignKey(JobseekerAccount, on_delete=models.CASCADE)
    vacancy = models.ForeignKey(Vacancy, on_delete=models.CASCADE)
    status = models.ForeignKey(JobApplicationStatus, on_delete=models.PROTECT)
    application_number = models.CharField(max_length=100, unique=True, blank=True)  # ← ADD THIS
    submitted_at = models.DateTimeField(auto_now_add=True)

    # ── Frozen profile snapshots at time of submission ─────────
    snapshot_basic        = models.JSONField(default=dict)
    snapshot_academic     = models.JSONField(default=list)
    snapshot_professional = models.JSONField(default=list)
    snapshot_work         = models.JSONField(default=list)
    snapshot_memberships  = models.JSONField(default=list)
    snapshot_referees     = models.JSONField(default=list)
    snapshot_additional   = models.JSONField(default=dict)

    # ── SCREENING ─────────────────────────────────────────────────────────
    # Set by system during auto-longlist. null = not yet screened.
    screening_passed = models.BooleanField(null=True, blank=True)
    screening_reasons = models.JSONField(default=list)  # internal/audit only — NEVER shown to applicant
    screening_flags = models.JSONField(default=list)  # soft warnings — committee sees on dossier
    screening_ran_at = models.DateTimeField(null=True, blank=True)

    # ── ASSIGNMENT ────────────────────────────────────────────────────────
    # Set by committee lead when distributing applications to officers
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='assigned_applications',
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='assignments_made',
    )
    assigned_at = models.DateTimeField(null=True, blank=True)

    # ── LONGLIST DECISION ─────────────────────────────────────────────────
    # Set by officer during manual longlist review
    longlist_decision = models.CharField(
        max_length=20,
        choices=[
            ('shortlisted', 'Shortlisted'),
            ('rejected', 'Rejected'),
            ('hold', 'Hold'),
        ],
        null=True, blank=True,
    )
    longlist_decision_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='longlist_decisions',
    )
    longlist_decision_at = models.DateTimeField(null=True, blank=True)
    longlist_notes = models.TextField(blank=True)

    class Meta:
        unique_together = ('user', 'vacancy')
        ordering        = ['-submitted_at']

    def __str__(self):
        return f"{self.user} — {self.vacancy.reference_number}"

class LonglistReviewLog(models.Model):
    ACTION_CHOICES = [
        ('viewed',           'Viewed Application'),
        ('shortlisted',      'Marked Shortlist'),
        ('rejected',         'Marked Reject'),
        ('held',             'Marked Hold'),
        ('override',         'Override System Decision'),
        ('assigned',         'Assigned to Officer'),
        ('bulk_shortlist',   'Bulk Shortlist'),
        ('bulk_reject',      'Bulk Reject'),
        ('bulk_assign',      'Bulk Assign'),
        ('note_added',       'Added Note'),
        ('decision_changed', 'Decision Changed'),
        ('system_screening', 'System Auto-Screening'),
    ]

    vacancy     = models.ForeignKey(Vacancy, on_delete=models.CASCADE, related_name='longlist_logs')
    application = models.ForeignKey(JobApplication, on_delete=models.CASCADE, related_name='longlist_logs', null=True, blank=True)
    officer     = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='longlist_logs', null=True, blank=True)
    action      = models.CharField(max_length=30, choices=ACTION_CHOICES)
    notes       = models.TextField(blank=True)
    metadata    = models.JSONField(default=dict)
    actioned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-actioned_at']

    def __str__(self):
        who = self.officer.get_full_name() if self.officer else 'System'
        app = f" — App #{self.application_id}" if self.application_id else ''
        return f"{who} | {self.get_action_display()}{app} | {self.actioned_at:%d %b %Y %H:%M}"


class JobApplicationStatusLog(models.Model):
    application = models.ForeignKey(
                      JobApplication,
                      on_delete=models.CASCADE,
                      related_name='status_logs'
                  )
    from_status = models.ForeignKey(
                      JobApplicationStatus,
                      on_delete=models.SET_NULL,
                      null=True, blank=True,
                      related_name='log_from'
                  )
    to_status   = models.ForeignKey(
                      JobApplicationStatus,
                      on_delete=models.SET_NULL,
                      null=True,
                      related_name='log_to'
                  )
    changed_by  = models.ForeignKey(
                      settings.AUTH_USER_MODEL,
                      on_delete=models.SET_NULL,
                      null=True, blank=True
                  )   # admin/HR user who made the change
    changed_at  = models.DateTimeField(auto_now_add=True)
    notes       = models.TextField(blank=True)

    class Meta:
        ordering = ['-changed_at']

    def __str__(self):
        return f"{self.application} → {self.to_status}"


class JobApplicationNotification(models.Model):
    TYPE_CHOICES = [
        ('application_submitted', 'Application Submitted'),
        ('status_changed',        'Status Changed'),
    ]

    user                = models.ForeignKey(
                              'accounts.JobseekerAccount',
                              on_delete=models.CASCADE,
                              related_name='notifications'
                          )
    title               = models.CharField(max_length=255)
    message             = models.TextField()
    notification_type   = models.CharField(max_length=50, choices=TYPE_CHOICES)
    is_read             = models.BooleanField(default=False)
    created_at          = models.DateTimeField(auto_now_add=True)
    related_application = models.ForeignKey(
                              JobApplication,
                              on_delete=models.SET_NULL,
                              null=True, blank=True
                          )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user} — {self.title}"

class VacancyApplicationCounter(models.Model):
    """
    Atomic per-vacancy sequence counter.
    Guarantees unique sequential application numbers even under concurrent submissions.
    """
    vacancy     = models.OneToOneField(
                      Vacancy, on_delete=models.CASCADE,
                      related_name='application_counter'
                  )
    last_number = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.vacancy.reference_number} — {self.last_number} applications"

# class ShortlistingCommittee(models.Model):
#     vacancy = models.OneToOneField(
#         Vacancy,
#         on_delete=models.CASCADE,
#         related_name='shortlisting_committee'
#     )

#     members = models.ManyToManyField(
#         settings.AUTH_USER_MODEL,
#         related_name='shortlisting_committees'
#     )

#     created_at = models.DateTimeField(auto_now_add=True)
    
   
class ShortlistingDecision(models.Model):
    application = models.ForeignKey(
        Application,
        on_delete=models.CASCADE,
        related_name='shortlisting_votes'
    )
    committee_member = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )
    decision = models.CharField(
        max_length=10,
        choices=[
            ('approve', 'Approve'),
            ('reject', 'Reject')
        ]
    )
    comment = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('application', 'committee_member')
        
   
class InterviewSection(models.Model):
    template = models.ForeignKey(
        InterviewTemplate,
        on_delete=models.CASCADE,
        related_name="sections"
    )
    name = models.CharField(max_length=255)
    max_score = models.DecimalField(max_digits=5, decimal_places=2)
    weight = models.DecimalField(max_digits=5, decimal_places=2, default=1)

    order = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.name} ({self.max_score})"
    
class InterviewSectionScore(models.Model):

    interview_score = models.ForeignKey(
        InterviewScore,
        on_delete=models.CASCADE,
        related_name="section_scores"
    )

    section = models.ForeignKey(
        InterviewSection,
        on_delete=models.CASCADE
    )

    score = models.DecimalField(max_digits=5, decimal_places=2)

    class Meta:
        unique_together = ("interview_score", "section")

class ShortlistingCommittee(models.Model):
    """
    Tracks which staff members have been appointed to the shortlisting
    committee for a given vacancy.
    """
    vacancy         = models.ForeignKey(
        'Vacancy', on_delete=models.CASCADE,
        related_name='shortlisting_committee'
    )
    member          = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='committee_assignments'
    )
    appointed_by    = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='committee_appointments_made'
    )
    appointed_at        = models.DateTimeField(default=timezone.now)
    is_active           = models.BooleanField(default=True)
    scores_submitted    = models.BooleanField(default=False)
    scores_submitted_at = models.DateTimeField(null=True, blank=True)
    picks_submitted     = models.BooleanField(default=False)
    picks_submitted_at  = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [('vacancy', 'member')]

    def __str__(self):
        return f"{self.member} on committee for {self.vacancy}"


class CommitteeScore(models.Model):
    """
    One member's score (1–100) for one application on one vacancy.
    Saved as draft until the member explicitly submits all their scores.
    """
    vacancy     = models.ForeignKey(
        'Vacancy', on_delete=models.CASCADE,
        related_name='committee_scores'
    )
    application = models.ForeignKey(
        'JobApplication', on_delete=models.CASCADE,
        related_name='committee_scores'
    )
    member      = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='committee_scores_given'
    )
    score        = models.PositiveSmallIntegerField()   # 1–100
    comment      = models.TextField()
    is_draft     = models.BooleanField(default=True)
    submitted    = models.BooleanField(default=False)
    created_at   = models.DateTimeField(default=timezone.now)
    submitted_at = models.DateTimeField(null=True, blank=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('vacancy', 'application', 'member')]

    def __str__(self):
        return f"{self.member} scored {self.application} → {self.score}"


class CommitteeScoreAmendment(models.Model):
    """
    Audit trail when a score is changed after submission (requires HR override).
    """
    score       = models.ForeignKey(
        'CommitteeScore', on_delete=models.CASCADE,
        related_name='amendments'
    )
    old_score   = models.PositiveSmallIntegerField()
    new_score   = models.PositiveSmallIntegerField()
    old_comment = models.TextField()
    new_comment = models.TextField()
    reason      = models.TextField()
    amended_by  = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='score_amendments'
    )
    amended_at  = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Amendment on score #{self.score_id}: {self.old_score} → {self.new_score}"


class ShortlistPick(models.Model):
    """
    Each committee member's include/exclude decision for each application,
    submitted after reviewing the ranked scores.
    """
    vacancy     = models.ForeignKey(
        'Vacancy', on_delete=models.CASCADE,
        related_name='shortlist_picks'
    )
    application = models.ForeignKey(
        'JobApplication', on_delete=models.CASCADE,
        related_name='shortlist_picks'
    )
    member      = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='shortlist_picks'
    )
    include    = models.BooleanField()   # True = include, False = exclude
    reason     = models.TextField()
    decided_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = [('vacancy', 'application', 'member')]

    def __str__(self):
        verb = "included" if self.include else "excluded"
        return f"{self.member} {verb} {self.application}"


class ShortlistConsent(models.Model):
    """
    Each committee member's consent/dissent on the final shortlist,
    submitted after all picks are done.
    50%+1 consents → HR can finalise.
    """
    RESPONSE_CHOICES = [
        ('consented',   'Consented'),
        ('dissented',   'Dissented'),
        ('no_response', 'No Response'),
    ]

    vacancy        = models.ForeignKey(
        'Vacancy', on_delete=models.CASCADE,
        related_name='shortlist_consents'
    )
    member         = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='shortlist_consents'
    )
    response       = models.CharField(
        max_length=20, choices=RESPONSE_CHOICES, default='no_response'
    )
    dissent_reason = models.TextField(blank=True)
    responded_at   = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [('vacancy', 'member')]

    def __str__(self):
        return f"{self.member} → {self.response} on {self.vacancy}"


class ShortlistLog(models.Model):
    """
    Full audit trail for every action taken during the shortlisting stage.
    application may be null for vacancy-level actions (e.g. member appointed).
    """
    vacancy            = models.ForeignKey(
        'Vacancy', on_delete=models.CASCADE,
        related_name='shortlist_logs'
    )
    application        = models.ForeignKey(
        'JobApplication', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='shortlist_logs'
    )
    performed_by       = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='shortlist_actions'
    )
    action             = models.CharField(max_length=50)
    notes              = models.TextField(blank=True)
    metadata           = models.JSONField(default=dict, blank=True)
    timestamp          = models.DateTimeField(default=timezone.now)
    performed_by_label = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.action} on {self.vacancy} at {self.timestamp:%Y-%m-%d %H:%M}"