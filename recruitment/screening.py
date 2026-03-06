"""
recruitment/screening.py

Screening engine for UFAA recruitment portal.
Pure Python — no Django ORM calls. Fully testable in isolation.

Confirmed snapshot field names (from DB inspection):
  snapshot_additional: cv_filename, cover_letter_filename, availability,
                       expected_salary, linkedin_url, portfolio_url, languages
  snapshot_academic:   education_level (string), institution, year_completed, grade
  snapshot_work:       job_title, company, start_display, end_display,
                       duties, is_current, employment_type, country, exit_reason
"""

from datetime import date, datetime


# ── Education level string → rank integer ──────────────────────────────────
# snapshot_academic stores education_level as a plain string e.g. "Bachelor's Degree"
# We map that string to a rank integer for comparison.
EDUCATION_LEVEL_RANKS = {
    'kenya certificate of primary education (kcpe)': 1,
    'kcpe': 1,
    'kenya certificate of secondary education (kcse)': 2,
    'kcse': 2,
    'o-levels': 2, 'o levels': 2, 'igcse': 2, 'ged': 2,
    'a-levels': 3, 'a levels': 3, 'international baccalaureate': 3, 'ib': 3,
    'certificate': 4,
    'diploma': 5,
    'higher national diploma': 6, 'hnd': 6,
    "bachelor's degree": 7, 'bachelors degree': 7, 'bachelor degree': 7, 'degree': 7,
    'postgraduate diploma': 8,
    "master's degree": 9, 'masters degree': 9, 'msc': 9, 'mba': 9,
    'phd': 10, 'doctorate': 10, 'phd / doctorate': 10,
    'other foreign qualification': 11,
}

EDUCATION_LEVEL_LABELS = {
    1: 'KCPE', 2: 'KCSE / O-Levels', 3: 'A-Levels / IB',
    4: 'Certificate', 5: 'Diploma', 6: 'Higher National Diploma (HND)',
    7: "Bachelor's Degree", 8: 'Postgraduate Diploma',
    9: "Master's Degree", 10: 'PhD / Doctorate', 11: 'Other Foreign Qualification',
}

FOREIGN_QUAL_LEVEL = 11

AVAILABILITY_DAYS = {
    'Immediately': 0, '1 Week Notice': 7, '2 Weeks Notice': 14,
    '3 Weeks Notice': 21, '1 Month Notice': 30,
    '2 Months Notice': 60, '3 Months Notice': 90, 'Not Available': 999,
}


def run_screening(snapshot: dict, criteria: dict,
                  submitted_at, vacancy_end_date) -> dict:
    """
    snapshot is built by _build_snapshot() in context_processor.
    It must contain keys: 'additional', 'academic', 'professional', 'work'
    pointing to the respective snapshot dicts/lists.
    """
    reasons = []
    flags   = []

    additional   = snapshot.get('additional',   {}) or {}
    academic     = snapshot.get('academic',     []) or []
    professional = snapshot.get('professional', []) or []
    work         = snapshot.get('work',         []) or []

    # ── Check 0: Late submission ───────────────────────────────────────────
    sub_date = submitted_at.date() if hasattr(submitted_at, 'date') else submitted_at
    if sub_date > vacancy_end_date:
        reasons.append(
            f"Application submitted after vacancy closing date "
            f"({sub_date.strftime('%d %b %Y')} — "
            f"vacancy closed {vacancy_end_date.strftime('%d %b %Y')})"
        )
        return {'passed': False, 'reasons': reasons, 'flags': flags}

    # ── Check 1: CV ────────────────────────────────────────────────────────
    if criteria.get('require_cv', True):
        # cv_filename is set when applicant uploads a CV
        if not additional.get('cv_filename'):
            reasons.append("CV not uploaded.")

    # ── Check 2: Cover letter ──────────────────────────────────────────────
    if criteria.get('require_cover_letter', True):
        if not additional.get('cover_letter_filename'):
            reasons.append("Cover letter not uploaded.")

    # ── Check 3: Education level ───────────────────────────────────────────
    min_edu_level = criteria.get('minimum_education_level', 0)
    if min_edu_level > 0:
        applicant_level = _highest_education_rank(academic)

        if applicant_level is None:
            reasons.append("No academic qualifications found in profile.")
        elif applicant_level == FOREIGN_QUAL_LEVEL:
            flags.append(
                "Applicant holds a foreign qualification — committee must verify "
                f"equivalence to minimum requirement "
                f"({EDUCATION_LEVEL_LABELS.get(min_edu_level, str(min_edu_level))})."
            )
        elif applicant_level < min_edu_level:
            reasons.append(
                f"Education level below minimum — "
                f"applicant: {EDUCATION_LEVEL_LABELS.get(applicant_level, f'Level {applicant_level}')}, "
                f"required: {EDUCATION_LEVEL_LABELS.get(min_edu_level, f'Level {min_edu_level}')}."
            )
        # NOTE: snapshot_academic has no certificate_uploaded field.
        # Academic cert check is SKIPPED — committee verifies documents manually.

    # ── Check 4: Professional qualification ───────────────────────────────
    if criteria.get('require_professional_qualification', False):
        if not professional:
            flags.append(
                "No professional qualification found — committee should verify "
                "if applicable qualification is embedded in CV."
            )

    # ── Check 5: Work experience ───────────────────────────────────────────
    min_exp_years = criteria.get('minimum_experience_years', 0)
    if min_exp_years > 0:
        total_months = _calculate_experience_months(work)
        if total_months / 12 < min_exp_years:
            reasons.append(
                f"Insufficient work experience — "
                f"required: {min_exp_years} year(s), "
                f"submitted: {total_months // 12} year(s) {total_months % 12} month(s)."
            )

    # ── Check 6: Salary affordability ─────────────────────────────────────
    if criteria.get('check_salary', False):
        salary_max = criteria.get('salary_max', 0)
        expected   = additional.get('expected_salary')
        if salary_max > 0 and expected:
            try:
                if int(expected) > salary_max:
                    flags.append(
                        f"Expected salary KES {int(expected):,} exceeds "
                        f"vacancy maximum KES {salary_max:,} — committee review recommended."
                    )
            except (ValueError, TypeError):
                pass

    # ── Check 7: Availability ──────────────────────────────────────────────
    if criteria.get('check_availability', False):
        max_notice_days = criteria.get('maximum_notice_days', 30)
        availability    = additional.get('availability', '')
        if availability == 'Not Available':
            reasons.append("Applicant marked as 'Not Available'.")
        elif availability:
            notice_days = AVAILABILITY_DAYS.get(availability, 0)
            if notice_days > max_notice_days:
                flags.append(
                    f"Notice period '{availability}' ({notice_days} days) "
                    f"exceeds vacancy maximum of {max_notice_days} days."
                )

    return {'passed': len(reasons) == 0, 'reasons': reasons, 'flags': flags}


# ── Helpers ────────────────────────────────────────────────────────────────

def _highest_education_rank(academic: list) -> int | None:
    """Convert education_level strings to ranks and return the highest."""
    if not academic:
        return None
    ranks = []
    for entry in academic:
        rank = _edu_string_to_rank(entry.get('education_level', ''))
        if rank is not None:
            ranks.append(rank)
    return max(ranks) if ranks else None


def _edu_string_to_rank(level_str: str) -> int | None:
    """Map education level string to rank integer via EDUCATION_LEVEL_RANKS."""
    if not level_str:
        return None
    normalised = level_str.strip().lower()
    if normalised in EDUCATION_LEVEL_RANKS:
        return EDUCATION_LEVEL_RANKS[normalised]
    # Partial match for variations like "Bachelor's Degree (Hons)"
    for key, rank in EDUCATION_LEVEL_RANKS.items():
        if key in normalised:
            return rank
    return None


def _calculate_experience_months(work: list) -> int:
    """
    Sum total months from snapshot_work.
    Uses start_display / end_display (e.g. 'March 2008', 'Present').
    """
    today = date.today()
    total = 0
    for job in work:
        try:
            start_str = job.get('start_display') or job.get('start_date') or ''
            end_str   = job.get('end_display')   or job.get('end_date')   or ''

            if not start_str:
                continue

            start = _parse_date(start_str)
            if start is None:
                continue

            if end_str and end_str.lower() not in ('present', '—', ''):
                end = _parse_date(end_str) or today
            else:
                end = today

            if end >= start:
                total += max((end.year - start.year) * 12 + (end.month - start.month), 0)
        except (ValueError, TypeError):
            continue
    return total


def _parse_date(s: str) -> date | None:
    """Parse ISO or human-readable date string."""
    if not s:
        return None
    for fmt in ('%Y-%m-%d', '%Y-%m', '%B %Y', '%b %Y', '%Y'):
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except ValueError:
            continue
    return None