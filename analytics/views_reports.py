"""
analytics/views_reports.py
===========================
All 18 reports. PDF via WeasyPrint, CSV via HttpResponse.

PDF templates inherit from analytics/reports/pdf/base_report.html
which has TODO markers for logo + signature block.

Install: pip install weasyprint

REPORT LIST
-----------
HR:      R01 Vacancy Summary, R02 Applicant Register, R03 Longlist,
         R04 Shortlist, R05 Interview Scores, R06 Appointment,
         R07 Diversity, R08 Pipeline Status (CSV), R09 Overrides,
         R10 Committee Activity, R11 Panel Activity
CEO:     R12 CEO Decision Log, R13 Top Candidates
Auditor: R14 Full Audit Trail, R15 Status Change Log (CSV),
         R16 Override Audit, R17 COI Declarations, R18 User Activity (CSV)
"""

import csv
import logging
from datetime import date

from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.template.loader import render_to_string
from django.utils import timezone

from core.decorators import role_required
from recruitment.models import (
    CommitteeVote, InterviewCriterion, InterviewLog, InterviewPanel,
    InterviewResult, InterviewScore, JobApplication,
    JobApplicationStatusLog, LonglistReviewLog, ShortlistingCommittee,
    ShortlistLog, ShortlistResult, Vacancy,
)

logger = logging.getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _render_pdf(template_name, context, filename='report.pdf'):
    html_string = render_to_string(template_name, context)
    try:
        from xhtml2pdf import pisa
        import io
        buffer = io.BytesIO()
        pisa.CreatePDF(html_string, dest=buffer)
        pdf_bytes = buffer.getvalue()
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    except ImportError:
        return HttpResponse(html_string, content_type='text/html')


def _csv_response(filename, headers, rows):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    import csv as _csv
    w = _csv.writer(response)
    w.writerow(headers)
    for row in rows:
        w.writerow(row)
    return response


def _base(vacancy=None, title='', code=''):
    """Base context shared by all PDF templates."""
    return {
        'report_title':   title,
        'report_code':    code,
        'generated_at':   timezone.now(),
        'generated_date': date.today().strftime('%d %B %Y'),
        'vacancy':        vacancy,
        # TODO: replace with confirmed client logo URL
        'logo_url': 'https://ufaa.go.ke/wp-content/uploads/2022/07/LOGO_RVSD-2-1.png',
    }


# ── Reports index pages ────────────────────────────────────────────────────────

@login_required
@role_required(['hod_hr'])
def hr_reports_index(request):
    vacancies = Vacancy.objects.exclude(status='draft').order_by('-created_at')
    return render(request, 'analytics/reports/hr_reports_index.html', {
        'page': 'HR Reports', 'vacancies': vacancies,
    })


@login_required
@role_required(['ceo'])
def ceo_reports_index(request):
    vacancies = Vacancy.objects.filter(
        status__in=['ceo_review', 'ceo_approved', 'appointed']
    ).order_by('-created_at')
    return render(request, 'analytics/reports/ceo_reports_index.html', {
        'page': 'CEO Reports', 'vacancies': vacancies,
    })


@login_required
@role_required(['auditor'])
def auditor_reports_index(request):
    vacancies = Vacancy.objects.exclude(status='draft').order_by('-created_at')
    return render(request, 'analytics/reports/auditor_reports_index.html', {
        'page': 'Auditor Reports', 'vacancies': vacancies,
    })


# ═══════════════════════════════════════════════════════════════════════════════
# HR REPORTS
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
@role_required(['hod_hr'])
def report_r01_vacancy_summary(request):
    fmt       = request.GET.get('fmt', 'pdf')
    vacancies = Vacancy.objects.exclude(status='draft').annotate(
        app_count=Count('jobapplication')
    ).order_by('-created_at')

    if fmt == 'csv':
        return _csv_response('R01_Vacancy_Summary.csv',
            ['Title','Reference','Type','Status','Start Date','End Date','Applications','Grade'],
            [[v.title, v.reference_number, v.get_vacancy_type_display(),
              v.status, v.start_date, v.end_date, v.app_count, v.grade_category]
             for v in vacancies])

    ctx = _base(title='Vacancy Summary Report', code='R01')
    ctx['vacancies'] = vacancies
    return _render_pdf('analytics/reports/pdf/r01_vacancy_summary.html',
                       ctx, 'R01_Vacancy_Summary.pdf')


@login_required
@role_required(['hod_hr'])
def report_r02_applicant_register(request, vacancy_id):
    fmt     = request.GET.get('fmt', 'pdf')
    vacancy = get_object_or_404(Vacancy, id=vacancy_id)
    apps    = JobApplication.objects.filter(vacancy=vacancy).select_related(
        'status', 'user'
    ).order_by('application_number')

    if fmt == 'csv':
        rows = []
        for app in apps:
            b = app.snapshot_basic or {}
            pwd = b.get('disability_status', '')
            rows.append([
                app.application_number,
                f"{b.get('first_name','')} {b.get('surname','')}".strip(),
                b.get('id_no', ''),
                app.user.email,
                b.get('phone_number', ''),
                b.get('gender', ''),
                b.get('home_county', ''),
                'Yes' if pwd and pwd.lower() not in ('', 'none', 'no') else 'No',
                app.status.name,
                app.submitted_at.strftime('%d %b %Y'),
            ])
        return _csv_response(f'R02_{vacancy.reference_number}_Applicants.csv',
            ['App No.','Name','ID No.','Email','Phone','Gender',
             'County','PWD','Status','Submitted'], rows)

    ctx = _base(vacancy=vacancy, title='Applicant Register', code='R02')
    ctx['apps'] = [{'app': a, 'basic': a.snapshot_basic or {}} for a in apps]
    return _render_pdf('analytics/reports/pdf/r02_applicant_register.html',
                       ctx, f'R02_{vacancy.reference_number}_Applicants.pdf')


@login_required
@role_required(['hod_hr'])
def report_r03_longlist(request, vacancy_id):
    vacancy = get_object_or_404(Vacancy, id=vacancy_id)
    apps    = JobApplication.objects.filter(
        vacancy=vacancy,
        status__code__in=['longlisted', 'final_longlisted', 'not_selected'],
    ).select_related('status', 'user').order_by('application_number')
    logs    = LonglistReviewLog.objects.filter(vacancy=vacancy).select_related(
        'application', 'officer'
    ).order_by('actioned_at')

    ctx = _base(vacancy=vacancy, title='Longlisting Report', code='R03')
    ctx.update({'apps': apps, 'logs': logs})
    return _render_pdf('analytics/reports/pdf/r03_longlist.html',
                       ctx, f'R03_{vacancy.reference_number}_Longlist.pdf')


@login_required
@role_required(['hod_hr'])
def report_r04_shortlist(request, vacancy_id):
    vacancy   = get_object_or_404(Vacancy, id=vacancy_id)
    results   = ShortlistResult.objects.filter(
        vacancy=vacancy
    ).select_related('application__user')
    committee = ShortlistingCommittee.objects.filter(
        vacancy=vacancy, is_active=True
    ).select_related('member')

    votes_by_app = {}
    for vote in CommitteeVote.objects.filter(
        vacancy=vacancy, is_draft=False
    ).select_related('member', 'application'):
        votes_by_app.setdefault(vote.application_id, []).append(vote)

    rows = []
    for r in results.order_by('-shortlisted', '-approve_count'):
        b = r.application.snapshot_basic or {}
        rows.append({
            'result': r,
            'basic':  b,
            'name':   f"{b.get('first_name','')} {b.get('surname','')}".strip(),
            'votes':  votes_by_app.get(r.application_id, []),
        })

    ctx = _base(vacancy=vacancy, title='Shortlisting Report', code='R04')
    ctx.update({'rows': rows, 'committee': committee})
    return _render_pdf('analytics/reports/pdf/r04_shortlist.html',
                       ctx, f'R04_{vacancy.reference_number}_Shortlist.pdf')


@login_required
@role_required(['hod_hr'])
def report_r05_interview_scores(request, vacancy_id):
    vacancy  = get_object_or_404(Vacancy, id=vacancy_id)
    results  = InterviewResult.objects.filter(
        vacancy=vacancy
    ).select_related('application__user').order_by('rank')
    criteria = InterviewCriterion.objects.filter(vacancy=vacancy).order_by('order')
    panel    = InterviewPanel.objects.filter(
        vacancy=vacancy, is_active=True, has_conflict=False
    ).select_related('member')

    scores_map = {}
    for s in InterviewScore.objects.filter(
        vacancy=vacancy, is_draft=False
    ).select_related('criterion', 'panel_member'):
        scores_map.setdefault(s.application_id, {}).setdefault(
            s.panel_member_id, {}
        )[s.criterion_id] = s

    rows = []
    for r in results:
        b = r.application.snapshot_basic or {}
        member_data = []
        for pm in panel:
            crit_scores = scores_map.get(r.application_id, {}).get(pm.member_id, {})
            member_data.append({
                'name':     f"{pm.member.first_name} {pm.member.last_name}".strip() or pm.member.email,
                'subtotal': sum(s.score for s in crit_scores.values()) if crit_scores else None,
                'crit_scores': {cid: s.score for cid, s in crit_scores.items()},
            })
        rows.append({
            'result':      r,
            'name':        f"{b.get('first_name','')} {b.get('surname','')}".strip(),
            'app_number':  r.application.application_number,
            'member_data': member_data,
        })

    ctx = _base(vacancy=vacancy, title='Interview Score Report', code='R05')
    ctx.update({'rows': rows, 'criteria': criteria, 'panel': panel})
    return _render_pdf('analytics/reports/pdf/r05_interview_scores.html',
                       ctx, f'R05_{vacancy.reference_number}_Scores.pdf')


@login_required
@role_required(['hod_hr'])
def report_r06_appointment(request, vacancy_id):
    vacancy = get_object_or_404(Vacancy, id=vacancy_id)
    winner  = JobApplication.objects.filter(
        vacancy=vacancy,
        status__code__in=['appointed', 'ceo_selected'],
    ).select_related('user', 'status').first()

    if not winner:
        from django.http import Http404
        raise Http404("No appointed candidate found for this vacancy.")

    try:
        result = InterviewResult.objects.get(vacancy=vacancy, application=winner)
    except InterviewResult.DoesNotExist:
        result = None

    ctx = _base(vacancy=vacancy, title='Appointment Report', code='R06')
    ctx.update({
        'winner':       winner,
        'basic':        winner.snapshot_basic        or {},
        'academic':     winner.snapshot_academic      or [],
        'professional': winner.snapshot_professional  or [],
        'work':         winner.snapshot_work          or [],
        'memberships':  winner.snapshot_memberships   or [],
        'referees':     winner.snapshot_referees      or [],
        'additional':   winner.snapshot_additional    or {},
        'result':       result,
        # TODO: add signature block — to be confirmed by client
    })
    return _render_pdf('analytics/reports/pdf/r06_appointment.html',
                       ctx, f'R06_{vacancy.reference_number}_Appointment.pdf')


@login_required
@role_required(['hod_hr'])
def report_r07_diversity(request):
    fmt        = request.GET.get('fmt', 'pdf')
    vacancy_id = request.GET.get('vacancy')

    if vacancy_id:
        apps  = JobApplication.objects.filter(vacancy_id=vacancy_id)
        title = f"Diversity Report — {Vacancy.objects.get(id=vacancy_id).reference_number}"
    else:
        apps  = JobApplication.objects.all()
        title = 'Diversity Report — All Vacancies'

    gender_c = {}
    county_c = {}
    edu_c    = {}
    pwd_total = 0

    for app in apps.select_related('status').only(
        'snapshot_basic', 'snapshot_academic', 'status'
    ):
        b     = app.snapshot_basic    or {}
        acad  = app.snapshot_academic or []
        g     = (b.get('gender')      or 'Unknown').strip()
        co    = (b.get('home_county') or 'Unknown').strip()
        disab = (b.get('disability_status') or '').lower()

        gender_c[g]  = gender_c.get(g, 0) + 1
        county_c[co] = county_c.get(co, 0) + 1
        if disab and disab not in ('', 'none', 'no', 'false'):
            pwd_total += 1
        for q in acad:
            lvl = (q.get('education_level') or 'Unknown').strip()
            edu_c[lvl] = edu_c.get(lvl, 0) + 1

    if fmt == 'csv':
        rows = []
        for g, c in sorted(gender_c.items()): rows.append(['Gender', g, c])
        for co, c in sorted(county_c.items(), key=lambda x: -x[1])[:20]:
            rows.append(['County', co, c])
        for e, c in sorted(edu_c.items(), key=lambda x: -x[1]):
            rows.append(['Education Level', e, c])
        rows.append(['PWD', 'Yes', pwd_total])
        return _csv_response('R07_Diversity.csv', ['Category', 'Value', 'Count'], rows)

    ctx = _base(title=title, code='R07')
    ctx.update({
        'gender_c':  dict(sorted(gender_c.items())),
        'county_c':  dict(sorted(county_c.items(), key=lambda x: -x[1])[:15]),
        'edu_c':     dict(sorted(edu_c.items(), key=lambda x: -x[1])),
        'pwd_total': pwd_total,
        'total_apps':apps.count(),
    })
    return _render_pdf('analytics/reports/pdf/r07_diversity.html',
                       ctx, 'R07_Diversity.pdf')


@login_required
@role_required(['hod_hr'])
def report_r08_pipeline_status(request):
    vacancies = Vacancy.objects.exclude(status='draft').annotate(
        app_count=Count('jobapplication')
    ).order_by('status', '-created_at')
    return _csv_response('R08_Pipeline_Status.csv',
        ['Title','Reference','Status','Grade','Type','Start','End','Applications'],
        [[v.title, v.reference_number, v.status, v.grade_category,
          v.vacancy_type, v.start_date, v.end_date, v.app_count]
         for v in vacancies])


@login_required
@role_required(['hod_hr'])
def report_r09_overrides(request):
    sl = ShortlistLog.objects.filter(
        action='override_approved'
    ).select_related('vacancy', 'application', 'performed_by').order_by('-timestamp')

    cl = list(InterviewLog.objects.filter(
        action='ceo_selection_made'
    ).select_related('vacancy', 'application', 'performed_by').order_by('-timestamp'))
    co = [e for e in cl if e.metadata.get('is_override')]

    ctx = _base(title='Override Report', code='R09')
    ctx.update({'shortlist_overrides': sl, 'ceo_overrides': co,
                'total': sl.count() + len(co)})
    return _render_pdf('analytics/reports/pdf/r09_overrides.html',
                       ctx, 'R09_Overrides.pdf')


@login_required
@role_required(['hod_hr'])
def report_r10_committee_activity(request, vacancy_id):
    vacancy   = get_object_or_404(Vacancy, id=vacancy_id)
    committee = ShortlistingCommittee.objects.filter(
        vacancy=vacancy, is_active=True
    ).select_related('member', 'appointed_by')

    rows = []
    for entry in committee:
        votes    = CommitteeVote.objects.filter(
            vacancy=vacancy, member=entry.member, is_draft=False)
        approved = votes.filter(approve=True).count()
        rejected = votes.filter(approve=False).count()
        total    = approved + rejected
        rows.append({
            'entry':    entry,
            'name':     f"{entry.member.first_name} {entry.member.last_name}".strip() or entry.member.email,
            'approved': approved,
            'rejected': rejected,
            'total':    total,
            'rate':     round(approved / total * 100, 1) if total else 0,
        })

    ctx = _base(vacancy=vacancy, title='Committee Activity Report', code='R10')
    ctx['rows'] = rows
    return _render_pdf('analytics/reports/pdf/r10_committee_activity.html',
                       ctx, f'R10_{vacancy.reference_number}_Committee.pdf')


@login_required
@role_required(['hod_hr'])
def report_r11_panel_activity(request, vacancy_id):
    vacancy  = get_object_or_404(Vacancy, id=vacancy_id)
    panel    = InterviewPanel.objects.filter(
        vacancy=vacancy, is_active=True
    ).select_related('member')
    criteria = InterviewCriterion.objects.filter(vacancy=vacancy)

    rows = []
    for entry in panel:
        scores = InterviewScore.objects.filter(
            vacancy=vacancy, panel_member=entry.member, is_draft=False)
        agg    = scores.aggregate(avg=Avg('score'))
        rows.append({
            'entry':  entry,
            'name':   f"{entry.member.first_name} {entry.member.last_name}".strip() or entry.member.email,
            'scored': scores.values('application_id').distinct().count(),
            'avg':    round(agg['avg'] or 0, 2),
            'coi':    entry.has_conflict,
            'reason': entry.conflict_reason,
        })

    ctx = _base(vacancy=vacancy, title='Panel Activity Report', code='R11')
    ctx.update({'rows': rows, 'criteria': criteria})
    return _render_pdf('analytics/reports/pdf/r11_panel_activity.html',
                       ctx, f'R11_{vacancy.reference_number}_Panel.pdf')


# ═══════════════════════════════════════════════════════════════════════════════
# CEO REPORTS
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
@role_required(['ceo'])
def report_r12_ceo_decisions(request):
    logs = InterviewLog.objects.filter(
        action='ceo_selection_made'
    ).select_related('vacancy', 'application', 'performed_by').order_by('-timestamp')

    rows = []
    for log in logs:
        by = log.performed_by
        rows.append({
            'log':      log,
            'vacancy':  log.vacancy,
            'winner':   log.metadata.get('selected_name', '—'),
            'rank':     log.metadata.get('rank', '—'),
            'override': log.metadata.get('is_override', False),
            'reason':   log.metadata.get('override_reason', ''),
            'by':       f"{by.first_name} {by.last_name}".strip() if by else '—',
        })

    ctx = _base(title='CEO Decision Log', code='R12')
    ctx['rows'] = rows
    return _render_pdf('analytics/reports/pdf/r12_ceo_decisions.html',
                       ctx, 'R12_CEO_Decisions.pdf')


@login_required
@role_required(['ceo'])
def report_r13_top_candidates(request, vacancy_id):
    vacancy  = get_object_or_404(Vacancy, id=vacancy_id)
    results  = InterviewResult.objects.filter(
        vacancy=vacancy
    ).select_related('application__user', 'application__status').order_by('rank')
    criteria = InterviewCriterion.objects.filter(vacancy=vacancy)

    rows = []
    for r in results:
        b = r.application.snapshot_basic or {}
        rows.append({
            'result': r,
            'name':   f"{b.get('first_name','')} {b.get('surname','')}".strip(),
            'app_no': r.application.application_number,
            'is_top': r.application.status.code == 'top_candidate',
        })

    ctx = _base(vacancy=vacancy, title='Top Candidates Report', code='R13')
    ctx.update({'rows': rows, 'criteria': criteria})
    return _render_pdf('analytics/reports/pdf/r13_top_candidates.html',
                       ctx, f'R13_{vacancy.reference_number}_TopCandidates.pdf')


# ═══════════════════════════════════════════════════════════════════════════════
# AUDITOR REPORTS
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
@role_required(['auditor'])
def report_r14_full_audit_trail(request, vacancy_id):
    vacancy = get_object_or_404(Vacancy, id=vacancy_id)
    ctx = _base(vacancy=vacancy, title='Full Audit Trail', code='R14')
    ctx.update({
        'status_logs': JobApplicationStatusLog.objects.filter(
            application__vacancy=vacancy
        ).select_related('application__user', 'from_status', 'to_status', 'changed_by').order_by('changed_at'),
        'shortlist_logs': ShortlistLog.objects.filter(
            vacancy=vacancy).select_related('performed_by').order_by('timestamp'),
        'interview_logs': InterviewLog.objects.filter(
            vacancy=vacancy).select_related('performed_by').order_by('timestamp'),
        'longlist_logs': LonglistReviewLog.objects.filter(
            vacancy=vacancy).select_related('officer').order_by('actioned_at'),
    })
    return _render_pdf('analytics/reports/pdf/r14_audit_trail.html',
                       ctx, f'R14_{vacancy.reference_number}_AuditTrail.pdf')


@login_required
@role_required(['auditor'])
def report_r15_status_change_log(request):
    vacancy_id = request.GET.get('vacancy')
    qs = JobApplicationStatusLog.objects.select_related(
        'application__vacancy', 'from_status', 'to_status', 'changed_by'
    ).order_by('changed_at')
    if vacancy_id:
        qs = qs.filter(application__vacancy_id=vacancy_id)

    rows = []
    for log in qs:
        rows.append([
            log.application.application_number or '—',
            log.application.vacancy.reference_number,
            log.from_status.code if log.from_status else '—',
            log.to_status.code   if log.to_status   else '—',
            str(log.changed_by)  if log.changed_by  else 'System',
            log.changed_at.strftime('%d %b %Y %H:%M'),
            (log.notes or '')[:200],
        ])
    return _csv_response('R15_Status_Change_Log.csv',
        ['App No.','Vacancy Ref','From Status','To Status',
         'Changed By','Changed At','Notes'], rows)


@login_required
@role_required(['auditor'])
def report_r16_override_audit(request):
    sl = ShortlistLog.objects.filter(
        action='override_approved'
    ).select_related('vacancy', 'application', 'performed_by').order_by('-timestamp')
    cl = list(InterviewLog.objects.filter(
        action='ceo_selection_made'
    ).select_related('vacancy', 'application', 'performed_by').order_by('-timestamp'))
    co = [e for e in cl if e.metadata.get('is_override')]

    ctx = _base(title='Override Audit Report', code='R16')
    ctx.update({'shortlist_overrides': sl, 'ceo_overrides': co})
    return _render_pdf('analytics/reports/pdf/r16_override_audit.html',
                       ctx, 'R16_Override_Audit.pdf')


@login_required
@role_required(['auditor'])
def report_r17_coi_declarations(request):
    ctx = _base(title='Conflict of Interest Declaration Report', code='R17')
    committee_coi = ShortlistingCommittee.objects.filter(
        has_conflict=True
    ).select_related('vacancy', 'member').order_by('-conflict_declared_at')
    panel_coi = InterviewPanel.objects.filter(
        has_conflict=True
    ).select_related('vacancy', 'member').order_by('-conflict_declared_at')
    ctx.update({
        'committee_coi': committee_coi,
        'panel_coi':     panel_coi,
        'total':         committee_coi.count() + panel_coi.count(),
    })
    return _render_pdf('analytics/reports/pdf/r17_coi_declarations.html',
                       ctx, 'R17_COI_Declarations.pdf')


@login_required
@role_required(['auditor'])
def report_r18_user_activity(request):
    rows = []

    for log in ShortlistLog.objects.select_related(
        'vacancy', 'performed_by'
    ).order_by('-timestamp'):
        rows.append([
            log.timestamp.strftime('%d %b %Y %H:%M'),
            log.action, 'Shortlist',
            log.vacancy.reference_number if log.vacancy else '—',
            log.performed_by_label or (str(log.performed_by) if log.performed_by else 'System'),
            (log.notes or '')[:200],
        ])

    for log in InterviewLog.objects.select_related(
        'vacancy', 'performed_by'
    ).order_by('-timestamp'):
        rows.append([
            log.timestamp.strftime('%d %b %Y %H:%M'),
            log.action, 'Interview',
            log.vacancy.reference_number if log.vacancy else '—',
            log.performed_by_label or (str(log.performed_by) if log.performed_by else 'System'),
            (log.notes or '')[:200],
        ])

    for log in LonglistReviewLog.objects.select_related(
        'vacancy', 'officer'
    ).order_by('-actioned_at'):
        rows.append([
            log.actioned_at.strftime('%d %b %Y %H:%M'),
            log.action, 'Longlist',
            log.vacancy.reference_number if log.vacancy else '—',
            str(log.officer) if log.officer else 'System',
            (log.notes or '')[:200],
        ])

    rows.sort(key=lambda r: r[0], reverse=True)
    return _csv_response('R18_User_Activity.csv',
        ['Timestamp','Action','Log Source','Vacancy','Performed By','Notes'], rows)