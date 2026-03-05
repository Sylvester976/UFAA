"""
recruitment/screening.py

Screening engine for UFAA recruitment portal.
Pure Python — no Django ORM calls. Fully testable in isolation.

Usage:
    from recruitment.screening import run_screening

    result = run_screening(
        snapshot        = app.snapshot_basic | app.snapshot_additional | ...,
        criteria        = vacancy.screening_criteria,
        submitted_at    = app.submitted_at,
        vacancy_end_date= vacancy.end_date,
    )
    app.screening_passed  = result['passed']
    app.screening_reasons = result['reasons']   # hard fails — internal only
    app.screening_flags   = result['flags']     # soft warnings — committee sees
    app.screening_ran_at  = timezone.now()
    app.save()
"""

from datetime import date, datetime
from dateutil.relativedelta import relativedelta


# ── Education level hierarchy ──────────────────────────────────────────────
# Mirrors EducationLevel.level values from migration 0026.
# Level integers are NOT unique — equivalent qualifications share the same level.
# e.g. KCSE, O-Levels, IGCSE, GED all = level 2.
# Screening uses >= comparison — ties are fine.
EDUCATION_LEVELS = {
    1:  "KCPE",
    2:  "KCSE / O-Levels / IGCSE / GED",
    3:  "A-Levels / IB",
    4:  "Certificate",
    5:  "Diploma",
    6:  "Higher National Diploma (HND)",
    7:  "Bachelor's Degree",
    9:  "Master's Degree",
    10: "PhD / Doctorate",
    11: "Other Foreign Qualification",  # soft flag — committee verifies equivalence
}

FOREIGN_QUAL_LEVEL = 11

# Availability choices → days mapping
AVAILABILITY_DAYS = {
    'Immediately':    0,
    '1 Week Notice':  7,
    '2 Weeks Notice': 14,
    '3 Weeks Notice': 21,
    '1 Month Notice': 30,
    '2 Months Notice':60,
    '3 Months Notice':90,
    'Not Available':  999,
}


def run_screening(snapshot: dict, criteria: dict,
                  submitted_at, vacancy_end_date) -> dict:
    """
    Run all screening checks for one application.

    Args:
        snapshot        : merged dict of all applicant snapshot fields
                          expects keys from: snapshot_basic, snapshot_additional,
                          snapshot_academic, snapshot_professional, snapshot_work
        criteria        : vacancy.screening_criteria JSON dict
        submitted_at    : application.submitted_at (datetime)
        vacancy_end_date: vacancy.end_date (date)

    Returns:
        {
            'passed' : bool   — False if any hard check fails
            'reasons': list   — hard fail reasons (internal/audit only)
            'flags'  : list   — soft warnings (committee sees on dossier)
        }
    """
    reasons = []   # hard fails
    flags   = []   # soft warnings

    # ── Check 0: Late submission (always runs, no criteria needed) ─────────
    sub_date = submitted_at.date() if hasattr(submitted_at, 'date') else submitted_at
    if sub_date > vacancy_end_date:
        reasons.append(
            f"Application submitted after vacancy closing date "
            f"({sub_date.strftime('%d %b %Y')} — "
            f"vacancy closed {vacancy_end_date.strftime('%d %b %Y')})"
        )
        # No point running further checks — immediately disqualified
        return {'passed': False, 'reasons': reasons, 'flags': flags}

    # ── Check 1: CV ────────────────────────────────────────────────────────
    if criteria.get('require_cv', True):
        cv = snapshot.get('cv') or snapshot.get('additional', {}).get('cv')
        if not cv:
            reasons.append("CV not uploaded.")

    # ── Check 2: Cover letter ──────────────────────────────────────────────
    if criteria.get('require_cover_letter', True):
        cl = (snapshot.get('cover_letter') or
              snapshot.get('additional', {}).get('cover_letter'))
        if not cl:
            reasons.append("Cover letter not uploaded.")

    # ── Check 3: Education level ───────────────────────────────────────────
    min_edu_level = criteria.get('minimum_education_level', 0)
    if min_edu_level > 0:
        academic = snapshot.get('academic', [])
        applicant_level = _highest_education_level(academic)

        if applicant_level is None:
            reasons.append(
                "No academic qualifications found in profile."
            )
        elif applicant_level == FOREIGN_QUAL_LEVEL:
            # Foreign qual — soft flag, committee verifies equivalence
            flags.append(
                "Applicant holds a foreign qualification — "
                "committee must verify equivalence to minimum requirement "
                f"({EDUCATION_LEVELS.get(min_edu_level, str(min_edu_level))})."
            )
        elif applicant_level < min_edu_level:
            applicant_label = EDUCATION_LEVELS.get(applicant_level, f"Level {applicant_level}")
            minimum_label   = EDUCATION_LEVELS.get(min_edu_level,   f"Level {min_edu_level}")
            reasons.append(
                f"Education level below minimum — "
                f"applicant: {applicant_label}, "
                f"required: {minimum_label}."
            )

        # Check 3b: academic cert uploaded for claimed highest qualification
        if criteria.get('require_academic_cert', True) and academic:
            highest = _highest_qualification_entry(academic)
            if highest and not highest.get('certificate_uploaded'):
                reasons.append(
                    f"Academic certificate not uploaded for claimed "
                    f"qualification: {highest.get('qualification_name', 'highest qualification')}."
                )

    # ── Check 4: Professional qualification ───────────────────────────────
    if criteria.get('require_professional_qualification', False):
        professional = snapshot.get('professional', [])
        if not professional:
            flags.append(
                "No professional qualification found — "
                "committee should verify if applicable qualification "
                "is embedded in CV."
            )

    # ── Check 5: Work experience ───────────────────────────────────────────
    min_exp_years = criteria.get('minimum_experience_years', 0)
    if min_exp_years > 0:
        work_history = snapshot.get('work', [])
        total_months = _calculate_experience_months(work_history)
        total_years  = total_months / 12

        if total_years < min_exp_years:
            reasons.append(
                f"Insufficient work experience — "
                f"required: {min_exp_years} year(s), "
                f"submitted: {total_months // 12} year(s) "
                f"{total_months % 12} month(s)."
            )

    # ── Check 6: Salary affordability ─────────────────────────────────────
    if criteria.get('check_salary', False):
        salary_max     = criteria.get('salary_max', 0)
        expected       = snapshot.get('additional', {}).get('expected_salary') or \
                         snapshot.get('expected_salary')
        if salary_max > 0 and expected:
            try:
                expected_int = int(expected)
                if expected_int > salary_max:
                    flags.append(
                        f"Expected salary KES {expected_int:,} exceeds "
                        f"vacancy maximum KES {salary_max:,} — "
                        f"committee review recommended."
                    )
            except (ValueError, TypeError):
                pass

    # ── Check 7: Availability / notice period ─────────────────────────────
    if criteria.get('check_availability', False):
        max_notice_days = criteria.get('maximum_notice_days', 30)
        availability    = (snapshot.get('additional', {}).get('availability') or
                           snapshot.get('availability', ''))

        if availability == 'Not Available':
            reasons.append("Applicant marked as 'Not Available'.")
        elif availability:
            notice_days = AVAILABILITY_DAYS.get(availability, 0)
            if notice_days > max_notice_days:
                flags.append(
                    f"Notice period '{availability}' ({notice_days} days) "
                    f"exceeds vacancy maximum of {max_notice_days} days — "
                    f"committee review recommended."
                )

    passed = len(reasons) == 0
    return {'passed': passed, 'reasons': reasons, 'flags': flags}


# ── Helpers ────────────────────────────────────────────────────────────────

def _highest_education_level(academic: list) -> int | None:
    """
    Return the highest EducationLevel.level integer from snapshot_academic.
    Returns None if list is empty.

    snapshot_academic entry expected shape:
    {
        'education_level_id': 7,      # EducationLevel.pk
        'education_level_name': '...',
        'education_level_value': 7,   # EducationLevel.rank  ← use this
        'institution': '...',
        'qualification_name': '...',
        'certificate_uploaded': True,
    }
    """
    if not academic:
        return None
    levels = []
    for entry in academic:
        lvl = entry.get('education_level_value') or entry.get('rank')
        if lvl is not None:
            levels.append(int(lvl))
    return max(levels) if levels else None


def _highest_qualification_entry(academic: list) -> dict | None:
    """Return the academic entry with the highest education level."""
    if not academic:
        return None
    return max(
        academic,
        key=lambda e: int(e.get('education_level_value') or e.get('level') or 0),
        default=None
    )


def _calculate_experience_months(work: list) -> int:
    """
    Sum total work experience in months from snapshot_work entries.
    Uses start_date and end_date strings (YYYY-MM-DD).
    If end_date is blank/null, uses today (still employed).
    Overlapping roles are NOT deduplicated — gross total.
    """
    today = date.today()
    total = 0
    for job in work:
        try:
            start_str = job.get('start_date') or ''
            end_str   = job.get('end_date')   or ''

            if not start_str:
                continue

            start = datetime.strptime(start_str[:10], '%Y-%m-%d').date()
            end   = datetime.strptime(end_str[:10],   '%Y-%m-%d').date() \
                    if end_str else today

            if end < start:
                continue

            diff   = relativedelta(end, start)
            months = diff.years * 12 + diff.months
            total += months
        except (ValueError, TypeError):
            continue

    return total