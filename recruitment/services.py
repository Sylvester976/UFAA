# recruitment/services.py

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