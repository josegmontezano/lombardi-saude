"""Navigation state for private clinic editorial and management pages."""
from .models import User
from .access_control import can_manage_clinic

SHELL_VIEWS = frozenset({
    "master_access", "management_access", "professional_access_home",
    "professional_posts", "professional_post_new", "professional_post_edit",
    "professional_analytics", "professional_submissions",
    "professional_submission_edit", "professional_instagram",
    "review_dashboard", "review_moderation", "professional_password_change",
})
POST_VIEWS = {"professional_posts", "professional_post_edit", "professional_post_new"}

def sidebar_context(request):
    user = request.user
    match = getattr(request, "resolver_match", None)
    name = match.url_name if match else ""
    authenticated = user.is_authenticated and user.is_active and user.role in (User.ADMIN, User.STAFF)
    active = (
        "overview" if name in ("master_access", "management_access", "professional_access_home")
        else "posts" if name in POST_VIEWS else
        "submissions" if name in ("professional_submissions", "professional_submission_edit") else
        "reviews" if name == "review_moderation" else
        "nps" if name == "review_dashboard" else
        "analytics" if name == "professional_analytics" else
        "instagram" if name == "professional_instagram" else
        "password" if name == "professional_password_change" else ""
    )
    return {
        "lx_admin_shell": authenticated and name in SHELL_VIEWS,
        "lx_admin_active": active,
        "lx_admin_manager": authenticated and can_manage_clinic(user),
        "lx_admin_publisher": authenticated and (
            user.role == User.ADMIN or
            (user.role == User.STAFF and user.staff_job == User.JOB_DOCTOR and user.is_staff)
        ),
    }
