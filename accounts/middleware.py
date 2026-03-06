from django.shortcuts import redirect
from django.urls import resolve

class LoginRequiredMiddleware:
    PUBLIC_VIEWS = {
        'landing',
        'index',
        'signup',
        'authregister',
        'authlogin',
        'logout',
        'verify_email',
        'send_verification_email',
        'vacancy_detail',
        'login',

        # dashboards
        'hr_dashboard',
        'panelist_dashboard',
        'shortlisting_dashboard',
        'ceo_dashboard',
        'test_dashbord',

        # users
        'user_list',
        'user_create',
        'user_update',
        'user_delete',
        'assign_role',

        # vacancy management
        'create_vacancy',
        'update_vacancy',
        'delete_vacancy',
        'publish_vacancy',
        'download_vacancy_pdf',

        # applications
        'hr_view_applications',
        'hr_applications_json',
        'committee_view_applications',
        'application_detail',

        # longlisting / shortlisting
        'start_longlisting',
        'shortlist_candidates',
        'move_to_longlisting',

        # panel appointment
        'appoint_panelists',
        'appoint_shortlisting_committee',

        # applicant area
        'apply_for_vacancy',
        'vacancy_panelists',
        'open_vacancy',
        'close_vacancy',

        # panelist actions
        'respond_panel_assignment',
        'panelist_interview_list',
        'panelist_score_candidate',
        'submit_shortlist',
        'panelist_submit_report',
        'panelist_reports',

        # HR ranking / selection
        'hr_ranking_view',
        'select_top_three',
        'hr_finalize_appointment',

        # CEO
        'ceo_review_view',
        'ceo_review',
        'ceo_approve',
        'ceo_select_candidate',

        # vacancy pipelines
        'vacancy_longlisting',
        'vacancy_shortlisting',
        'vacancy_interviews',
        'vacancy_list',
        'vacancy_appointments',

        # interview templates
        'template_list',
        'template_create',
        'template_detail',
        'template_edit',
        'template_delete',

        # sections
        'section_create',
        'section_edit',
        'section_delete',
    }
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        # Always allow admin
        if request.path.startswith('/admin/'):
            return self.get_response(request)

        try:
            current_view = resolve(request.path_info).view_name
        except:
            current_view = None

        # If public view → allow
        if current_view in self.PUBLIC_VIEWS:
            return self.get_response(request)

        # Otherwise require login
        if not request.session.get('user_id'):
            return redirect('/login/')

        return self.get_response(request)