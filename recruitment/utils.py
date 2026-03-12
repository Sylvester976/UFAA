# from recruitment.models import InterviewScore, PanelAssignment
#
#
# def check_and_lock_application(application):
#     vacancy = application.vacancy
#
#     total_panelists = PanelAssignment.objects.filter(
#         vacancy=vacancy
#     ).count()
#
#     total_scores = InterviewScore.objects.filter(
#         application=application
#     ).count()
#
#     if total_panelists > 0 and total_scores == total_panelists:
#         application.interview_locked = True
#         application.status = 'interviewed'
#         application.save()