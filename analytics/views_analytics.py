"""
analytics/views_analytics.py
"""
import json
import logging
from collections import Counter

from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db.models import Avg, Count, Max, Min, Q, Sum
from django.db.models.functions import TruncMonth
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from core.decorators import role_required
from recruitment.models import (
    CommitteeVote, InterviewLog, InterviewPanel, InterviewResult,
    InterviewScore, JobApplication, JobApplicationStatusLog,
    LonglistReviewLog, ShortlistingCommittee, ShortlistLog, Vacancy,
)
from analytics.models import VacancyAnalyticsSnapshot

logger  = logging.getLogger(__name__)
CACHE_TTL = 60 * 60


def _cached(key, fn, ttl=CACHE_TTL):
    data = cache.get(key)
    if data is None:
        data = fn()
        cache.set(key, data, ttl)
    return data


def _funnel_data(qs):
    agg = qs.aggregate(
        total=Sum('total_apps'), longlisted=Sum('longlisted'),
        shortlisted=Sum('shortlisted'), interviewed=Sum('interviewed'),
        appointed=Sum('appointed'),
    )
    return {
        'labels': ['Applications','Longlisted','Shortlisted','Interviewed','Appointed'],
        'values': [agg['total'] or 0, agg['longlisted'] or 0,
                   agg['shortlisted'] or 0, agg['interviewed'] or 0,
                   agg['appointed'] or 0],
    }


def _cycle_time_data(qs):
    agg = qs.aggregate(
        open=Avg('days_open'), longlist=Avg('days_longlisting'),
        shortlist=Avg('days_shortlisting'), interviews=Avg('days_interviews'),
        total=Avg('days_total'),
    )
    return {
        'labels': ['Open Period','Longlisting','Shortlisting','Interviews','Full Cycle'],
        'values': [round(agg['open'] or 0,1), round(agg['longlist'] or 0,1),
                   round(agg['shortlist'] or 0,1), round(agg['interviews'] or 0,1),
                   round(agg['total'] or 0,1)],
    }


def _aggregate_demographics(qs):
    gender, county, edu, pwd = Counter(), Counter(), Counter(), 0
    for s in qs:
        for k, v in (s.gender_breakdown or {}).items(): gender[k] += v
        for k, v in (s.county_breakdown or {}).items(): county[k] += v
        for k, v in (s.edu_level_breakdown or {}).items(): edu[k] += v
        pwd += s.pwd_count or 0
    return {'gender': dict(gender.most_common()),
            'county': dict(county.most_common(15)),
            'edu':    dict(edu.most_common()), 'pwd': pwd}


def _status_counts():
    return dict(Vacancy.objects.values('status')
                .annotate(c=Count('id')).values_list('status','c'))


# ── HR ─────────────────────────────────────────────────────────────────────────

@login_required
@role_required(['hod_hr'])
def hr_analytics_dashboard(request):
    def _build():
        snaps = VacancyAnalyticsSnapshot.objects.select_related('vacancy')
        demo  = _aggregate_demographics(snaps)
        monthly = (JobApplication.objects
                   .annotate(month=TruncMonth('submitted_at'))
                   .values('month').annotate(count=Count('id')).order_by('month'))
        from datetime import timedelta
        cutoff = timezone.now() - timedelta(days=30)
        return {
            'total_vacancies': Vacancy.objects.count(),
            'total_apps':      JobApplication.objects.count(),
            'total_appointed': JobApplication.objects.filter(status__code='appointed').count(),
            'avg_cycle_days':  round(snaps.aggregate(a=Avg('days_total'))['a'] or 0, 1),
            'ceo_overrides':   snaps.filter(ceo_override=True).count(),
            'stuck_count':     Vacancy.objects.filter(
                                   status__in=['longlisting','committee_stage','shortlisting',
                                               'interview_scheduling','ceo_review'],
                                   created_at__lt=cutoff).count(),
            'coi_total':       ShortlistingCommittee.objects.filter(has_conflict=True).count(),
            'override_total':  ShortlistLog.objects.filter(action='override_approved').count(),
            'pwd_total':       demo['pwd'],
            'status_counts':   _status_counts(),
            'score_stats':     InterviewResult.objects.aggregate(
                                   avg=Avg('percentage'), mx=Max('percentage'), mn=Min('percentage')),
            'top_vacancies':   list(Vacancy.objects.annotate(app_count=Count('jobapplication'))
                                    .order_by('-app_count')[:10]
                                    .values('id','title','reference_number','status','app_count')),
            'funnel_json':     json.dumps(_funnel_data(snaps)),
            'cycle_json':      json.dumps(_cycle_time_data(snaps)),
            'gender_json':     json.dumps({'labels': list(demo['gender'].keys()),
                                           'values': list(demo['gender'].values())}),
            'county_json':     json.dumps({'labels': list(demo['county'].keys()),
                                           'values': list(demo['county'].values())}),
            'monthly_json':    json.dumps({
                                   'labels': [m['month'].strftime('%b %Y') for m in monthly if m['month']],
                                   'values': [m['count'] for m in monthly if m['month']]}),
        }
    data = _cached('hr_analytics_main', _build)
    return render(request, 'analytics/dashboards/hr_analytics.html', {'page':'HR Analytics', **data})


@login_required
@role_required(['hod_hr'])
def hr_vacancy_analytics(request, vacancy_id):
    vacancy  = get_object_or_404(Vacancy, id=vacancy_id)
    snapshot = VacancyAnalyticsSnapshot.objects.filter(vacancy=vacancy).first()
    apps     = JobApplication.objects.filter(vacancy=vacancy).select_related('status')
    results  = InterviewResult.objects.filter(vacancy=vacancy).select_related('application__user','application__status').order_by('rank')
    panel    = InterviewPanel.objects.filter(vacancy=vacancy, is_active=True).select_related('member')
    committee= ShortlistingCommittee.objects.filter(vacancy=vacancy, is_active=True).select_related('member')
    logs     = JobApplicationStatusLog.objects.filter(application__vacancy=vacancy).select_related('from_status','to_status','changed_by').order_by('changed_at')
    ps = {}
    for pm in panel:
        agg  = InterviewScore.objects.filter(vacancy=vacancy, panel_member=pm.member, is_draft=False).aggregate(avg=Avg('score'), total=Sum('score'))
        name = f"{pm.member.first_name} {pm.member.last_name}".strip() or pm.member.email
        ps[pm.member_id] = {'name': name, 'avg': round(agg['avg'] or 0, 2), 'total': round(agg['total'] or 0, 2)}
    funnel = {'labels':['Applications','Longlisted','Shortlisted','Interviewed','Appointed'],
              'values':[apps.count(), apps.filter(status__code='longlisted').count(),
                        apps.filter(status__code='shortlisted').count(),
                        apps.filter(status__code='interviewed').count(),
                        apps.filter(status__code='appointed').count()]}
    return render(request, 'analytics/dashboards/hr_vacancy_analytics.html', {
        'page': f'Analytics — {vacancy.title}', 'vacancy': vacancy, 'snapshot': snapshot,
        'apps': apps, 'results': results, 'panel': panel, 'committee': committee, 'logs': logs,
        'panelist_scores': ps,
        'funnel_json':   json.dumps(funnel),
        'panelist_json': json.dumps({'labels':[v['name'] for v in ps.values()],
                                     'values':[v['total'] for v in ps.values()]}),
    })


@login_required
@role_required(['hod_hr'])
def hr_chart_funnel(request):
    return JsonResponse(_funnel_data(VacancyAnalyticsSnapshot.objects.all()))

@login_required
@role_required(['hod_hr'])
def hr_chart_cycle(request):
    return JsonResponse(_cycle_time_data(VacancyAnalyticsSnapshot.objects.all()))

@login_required
@role_required(['hod_hr'])
def hr_chart_gender(request):
    d = _aggregate_demographics(VacancyAnalyticsSnapshot.objects.all())
    return JsonResponse({'labels': list(d['gender'].keys()), 'values': list(d['gender'].values())})

@login_required
@role_required(['hod_hr'])
def hr_chart_county(request):
    d = _aggregate_demographics(VacancyAnalyticsSnapshot.objects.all())
    return JsonResponse({'labels': list(d['county'].keys()), 'values': list(d['county'].values())})

@login_required
@role_required(['hod_hr'])
def hr_chart_monthly(request):
    monthly = (JobApplication.objects.annotate(month=TruncMonth('submitted_at'))
               .values('month').annotate(count=Count('id')).order_by('month'))
    return JsonResponse({'labels':[m['month'].strftime('%b %Y') for m in monthly if m['month']],
                         'values':[m['count'] for m in monthly if m['month']]})


@login_required
@role_required(['hod_hr'])
def hr_analytics_refresh(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required.'}, status=405)
    from analytics.utils import build_snapshot
    rebuilt = errors = 0
    for v in Vacancy.objects.exclude(status='draft'):
        try:
            build_snapshot(v); rebuilt += 1
        except Exception as e:
            logger.error(f"Refresh failed vacancy {v.id}: {e}", exc_info=True); errors += 1
    cache.delete('hr_analytics_main'); cache.delete('ceo_analytics_main')
    return JsonResponse({'success': True, 'rebuilt': rebuilt, 'errors': errors,
                         'message': f'{rebuilt} snapshot(s) refreshed.'})


# ── CEO ────────────────────────────────────────────────────────────────────────

@login_required
@role_required(['ceo'])
def ceo_analytics_dashboard(request):
    def _build():
        snaps = VacancyAnalyticsSnapshot.objects.select_related('vacancy')
        total = snaps.count()
        over  = snaps.filter(ceo_override=True).count()
        avg_r = snaps.aggregate(a=Avg('ceo_selected_rank'))['a']
        return {
            'total_reviewed':    total,
            'total_overrides':   over,
            'override_rate':     round(over / total * 100, 1) if total else 0,
            'avg_selected_rank': round(avg_r, 1) if avg_r else '—',
            'pending': list(Vacancy.objects.filter(status='ceo_review')
                            .annotate(candidate_count=Count('jobapplication',
                                filter=Q(jobapplication__status__code='top_candidate')))
                            .values('id','title','reference_number','candidate_count')),
            'recent':  list(Vacancy.objects.filter(status__in=['ceo_approved','appointed'])
                            .order_by('-created_at')[:10]
                            .values('id','title','reference_number','status')),
            'override_json': json.dumps({'labels':['Within Top 3','Override'],
                                         'values':[total - over, over]}),
        }
    data = _cached('ceo_analytics_main', _build, ttl=60*30)
    return render(request, 'analytics/dashboards/ceo_analytics.html', {'page':'CEO Analytics', **data})


# ── Committee ──────────────────────────────────────────────────────────────────

@login_required
@role_required(['committee'])
def committee_analytics_dashboard(request):
    user = request.user
    rows = []
    for entry in ShortlistingCommittee.objects.filter(member=user, is_active=True).select_related('vacancy'):
        mv = CommitteeVote.objects.filter(vacancy=entry.vacancy, member=user, is_draft=False)
        ap = mv.filter(approve=True).count()
        re = mv.filter(approve=False).count()
        t  = ap + re
        rows.append({'vacancy': entry.vacancy, 'entry': entry,
                     'app_count': JobApplication.objects.filter(vacancy=entry.vacancy, status__code='final_longlisted').count(),
                     'voted': t, 'approved': ap, 'rejected': re,
                     'approval_rate': round(ap / t * 100, 1) if t else 0})
    oa = sum(r['approved'] for r in rows)
    or_ = sum(r['rejected'] for r in rows)
    ot  = oa + or_
    return render(request, 'analytics/dashboards/committee_analytics.html', {
        'page':'My Committee Analytics', 'rows': rows,
        'total_assignments': len(rows), 'overall_approved': oa,
        'overall_rejected': or_,
        'overall_rate': round(oa / ot * 100, 1) if ot else 0,
        'vote_json': json.dumps({'labels':['Approved','Disapproved'],'values':[oa, or_]}),
    })


# ── Panelist ───────────────────────────────────────────────────────────────────

@login_required
@role_required(['panelist'])
def panel_analytics_dashboard(request):
    user = request.user
    rows = []
    for entry in InterviewPanel.objects.filter(member=user, is_active=True).select_related('vacancy'):
        ms  = InterviewScore.objects.filter(vacancy=entry.vacancy, panel_member=user, is_draft=False)
        agg = ms.aggregate(avg=Avg('score'), total=Sum('score'))
        rows.append({'vacancy': entry.vacancy, 'entry': entry,
                     'scored_apps': ms.values('application_id').distinct().count(),
                     'avg_score':   round(agg['avg'] or 0, 2),
                     'total_score': round(agg['total'] or 0, 2)})
    all_s   = list(InterviewScore.objects.filter(panel_member=user, is_draft=False).values_list('score', flat=True))
    buckets = [(0,20),(20,40),(40,60),(60,80),(80,101)]
    return render(request, 'analytics/dashboards/panel_analytics.html', {
        'page':'My Panel Analytics', 'rows': rows,
        'total_assignments': len(rows), 'total_scored': sum(r['scored_apps'] for r in rows),
        'overall_avg': round(sum(r['avg_score'] for r in rows)/len(rows),2) if rows else 0,
        'score_dist_json': json.dumps({'labels':['0-20','20-40','40-60','60-80','80-100'],
                                       'values':[sum(1 for s in all_s if lo<=float(s)<hi) for lo,hi in buckets]}),
    })


# ── Auditor ────────────────────────────────────────────────────────────────────

@login_required
@role_required(['auditor'])
def auditor_analytics_dashboard(request):
    from datetime import timedelta
    so = ShortlistLog.objects.filter(action='override_approved').select_related('vacancy','performed_by').order_by('-timestamp')[:50]
    cl = list(InterviewLog.objects.filter(action='ceo_selection_made').select_related('vacancy','application','performed_by').order_by('-timestamp'))
    co = [e for e in cl if e.metadata.get('is_override')]
    today = timezone.now().date()
    overdue = []
    for v in Vacancy.objects.filter(status__in=['committee_stage','shortlisting','interview_scheduling','interviews','ceo_review','ceo_approved','appointed']):
        dl = v.end_date + timedelta(days=21)
        pm = ShortlistingCommittee.objects.filter(vacancy=v, is_active=True, has_conflict=False, votes_submitted=False)
        if pm.exists() and today > dl:
            overdue.append({'vacancy':v,'pending_count':pm.count(),'deadline':dl,'days_overdue':(today-dl).days})
    return render(request, 'analytics/dashboards/auditor_analytics.html', {
        'page':'Auditor Dashboard',
        'shortlist_overrides': so, 'ceo_overrides': co,
        'committee_coi': ShortlistingCommittee.objects.filter(has_conflict=True).select_related('vacancy','member').order_by('-conflict_declared_at'),
        'panel_coi': InterviewPanel.objects.filter(has_conflict=True).select_related('vacancy','member').order_by('-conflict_declared_at'),
        'overdue_committee': overdue,
        'total_status_changes': JobApplicationStatusLog.objects.count(),
        'changes_today': JobApplicationStatusLog.objects.filter(changed_at__date=today).count(),
        'shortlist_log_counts': dict(ShortlistLog.objects.values('action').annotate(c=Count('id')).values_list('action','c')),
        'interview_log_counts': dict(InterviewLog.objects.values('action').annotate(c=Count('id')).values_list('action','c')),
        'total_vacancies': Vacancy.objects.count(),
        'total_apps': JobApplication.objects.count(),
        'vacancies': Vacancy.objects.exclude(status='draft').order_by('-created_at'),
    })


@login_required
@role_required(['auditor'])
def auditor_vacancy_trail(request, vacancy_id):
    vacancy = get_object_or_404(Vacancy, id=vacancy_id)
    return render(request, 'analytics/dashboards/auditor_vacancy_trail.html', {
        'page': f'Audit Trail — {vacancy.reference_number}', 'vacancy': vacancy,
        'status_logs':    JobApplicationStatusLog.objects.filter(application__vacancy=vacancy).select_related('application__user','from_status','to_status','changed_by').order_by('changed_at'),
        'shortlist_logs': ShortlistLog.objects.filter(vacancy=vacancy).select_related('performed_by').order_by('-timestamp'),
        'interview_logs': InterviewLog.objects.filter(vacancy=vacancy).select_related('performed_by').order_by('-timestamp'),
        'longlist_logs':  LonglistReviewLog.objects.filter(vacancy=vacancy).select_related('officer').order_by('-actioned_at'),
    })


# ── Admin ──────────────────────────────────────────────────────────────────────

@login_required
@role_required(['admin'])
def admin_analytics_dashboard(request):
    from django.contrib.auth import get_user_model
    from recruitment.models import UFAAStaffNumber
    User = get_user_model()
    i = User.objects.filter(user_type=2, is_active=True).count()
    e = User.objects.filter(user_type=1, is_active=True).count()
    sc = _status_counts()
    return render(request, 'analytics/dashboards/admin_analytics.html', {
        'page':'Admin Analytics',
        'internal_users': i, 'external_users': e,
        'unverified': User.objects.filter(is_verified=False, user_type=1).count(),
        'staff_numbers': UFAAStaffNumber.objects.filter(is_active=True).count(),
        'vacancy_counts': sc, 'total_apps': JobApplication.objects.count(),
        'snapshots_count': VacancyAnalyticsSnapshot.objects.count(),
        'last_snap': VacancyAnalyticsSnapshot.objects.order_by('-snapped_at').first(),
        'user_type_json': json.dumps({'labels':['Internal Staff','External Applicants'],'values':[i,e]}),
        'status_json': json.dumps({'labels':list(sc.keys()),'values':list(sc.values())}),
    })