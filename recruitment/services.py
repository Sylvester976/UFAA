# recruitment/services.py

from recruitment.models import Application, PanelAssignment, ShortlistVote


def build_profile_snapshot(user):
    profile = user.profile

    return {
        "personal_details": {
            "salutation": profile.salutation,
            "surname": profile.surname,
            "first_name": profile.first_name,
            "second_name": profile.second_name,
            "email": profile.email,
            "id_no": profile.id_no,
            "phone_number": profile.phone_number,
            "date_of_birth": str(profile.date_of_birth) if profile.date_of_birth else None,
            "gender": profile.gender.name if profile.gender else None,
            "ethnic_group": profile.ethnic_group.name if profile.ethnic_group else None,
            "home_county": profile.home_county.name if profile.home_county else None,
        },

        "academic_qualifications": [
            {
                "education_level": q.education_level.name,
                "institution": q.institution,
                "field_of_study": q.field_of_study,
                "year_completed": q.year_completed,
                "grade": q.grade,
                "country": q.country,
            }
            for q in user.academic_qualifications.all()
        ],

        "professional_qualifications": [
            {
                "qualification": p.qualification,
                "awarding_body": p.awarding_body,
                "year_obtained": p.year_obtained,
                "expiry_year": p.expiry_year,
                "grade": p.grade,
                "country": p.country,
            }
            for p in user.professional_qualifications.all()
        ],

        "work_history": [
            {
                "job_title": w.job_title,
                "company": w.company,
                "employment_type": w.employment_type,
                "start": w.start_display,
                "end": w.end_display,
                "duties": w.duties,
                "country": w.country,
            }
            for w in user.work_history.all()
        ],
    }
    
    
def is_shortlisting_complete(vacancy):

    committee_members = PanelAssignment.objects.filter(
        vacancy=vacancy,
        committee_type='shortlisting',
        status='accepted'
    ).count()

    members_who_submitted = ShortlistVote.objects.filter(
        vacancy=vacancy
    ).values('committee_member').distinct().count()

    return committee_members > 0 and committee_members == members_who_submitted


from django.db.models import Count

def aggregate_shortlist(vacancy):

    total_members = PanelAssignment.objects.filter(
        vacancy=vacancy,
        committee_type='shortlisting',
        status='accepted'
    ).count()

    majority_threshold = (total_members // 2) + 1

    applications = Application.objects.filter(
        vacancy=vacancy,
        status='submitted'
    )

    for app in applications:

        vote_count = ShortlistVote.objects.filter(
            vacancy=vacancy,
            application=app
        ).count()

        if vote_count >= majority_threshold:
            app.move_to('shortlisted')
        else:
            app.move_to('not_selected')

    vacancy.move_to('shortlisting')