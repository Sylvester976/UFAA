from django.shortcuts import redirect
from django.urls import resolve
from django.conf import settings

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
        'forgot_password',
        'dashboard_logout',
        'send_reset_link',
        'reset_password',
        'do_reset_password',

        # dashboards
        'hr_dashboard',
        'panelist_dashboard',
        'shortlisting_dashboard',
        'ceo_dashboard',
        'test_dashbord',
        'redirect_dashboard',
        'admin_dashboard',

        # users
        'user_list',
        'user_create',
        'user_update',
        'user_delete',
        'assign_role',
        'staff_forgot_password',
        'staff_reset_password',
        'staff_do_reset_password',
        'staff_send_reset_link',
        'user_activate',
        'user_deactivate',

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
        'submit_shortlist',


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
        'hr_longlist_dashboard',
        'hr_longlist_dossier',
        'hr_longlist_decision',
        'hr_longlist_bulk',
        'hr_longlist_recall',
        'hr_longlist_finalise',
        'vacancy_shortlisting',
        'hr_appoint_committee',
        'hr_committee_progress',
        'hr_committee_staff_search',
        'hr_committee_notify',
        'hr_committee_remove',
        'hr_committee_add',
        'hr_shortlist_review',
        'hr_shortlist_override',
        'hr_shortlist_finalise',
        '_notify_rejected_applicants',
        '_notify_shortlisted_applicants',


        #commitee
        'committee_dashboard',
        'committee_acknowledge',
        'committee_review',
        'committee_vote_save',
        'committee_submit_all',
        'committee_results',
        'committee_declare_coi',

        # panel / interview (HR)
        'hr_interview_setup',
        'hr_panel_add',
        'hr_panel_remove',
        'hr_panel_notify',
        'hr_panel_staff_search',
        'hr_criteria_save',
        'hr_slots_save',
        'hr_interview_notify',
        'hr_interview_progress',
        'hr_interview_results',
        'vacancy_interviews',

        # panel member portal
        'panel_dashboard',
        'panel_acknowledge',
        'panel_declare_coi',
        'panel_score',
        'panel_score_save',
        'panel_submit_all',
        'panel_results',






        # sections
        'section_create',
        'section_edit',
        'section_delete',
        
        # permissions
        'permission_list',
        'permission_create',
        'permission_update',
        'permission_delete',

        # roles
        'role_list',
        'role_create',
        'role_update',
        'role_delete',
    }
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        # Allow admin
        if request.path.startswith('/admin/'):
            return self.get_response(request)

        # Allow static files
        if request.path.startswith(settings.STATIC_URL):
            return self.get_response(request)

        # Allow media files
        if request.path.startswith(settings.MEDIA_URL):
            return self.get_response(request)

        try:
            current_view = resolve(request.path_info).view_name
        except:
            current_view = None

        # Allow public views
        if current_view in self.PUBLIC_VIEWS:
            return self.get_response(request)

        # Require login
        if not request.session.get('user_id'):
            return redirect('/login/')

        return self.get_response(request)