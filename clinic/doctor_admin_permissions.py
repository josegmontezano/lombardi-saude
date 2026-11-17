"""Database-level Django Admin permissions for approved clinical managers.

Permitted models match the advanced-management screens that the project
already exposes. Doctor access never grants implicit user, group, billing,
or other unreviewed database privileges.
"""
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType

MEDICAL_MANAGER_GROUP = "Lombardi - Gestao Medica"

ADVANCED_PERMISSIONS = {
    "vlogvideo": ("view", "add", "change", "delete"),
    "websitevisit": ("view",),
    "visitorsubmission": ("view", "change"),
    "instagramentry": ("view",),
    "clinicreview": ("view",),
    "staffaccessrequest": ("view",),
}


def ensure_medical_admin_group(using="default"):
    """Called after migrate so content types and default permissions exist."""
    from .models import User
    group, _ = Group.objects.using(using).get_or_create(name=MEDICAL_MANAGER_GROUP)
    codes = [f"{action}_{model}" for model, actions in ADVANCED_PERMISSIONS.items() for action in actions]
    perms = Permission.objects.using(using).filter(content_type__app_label="clinic", codename__in=codes)
    if perms.exists():
        group.permissions.set(perms)
    doctors = User.objects.using(using).filter(
        is_active=True, role=User.STAFF, staff_job=User.JOB_DOCTOR, is_staff=True
    )
    for person in doctors.iterator():
        person.groups.add(group)
    return group


def sync_medical_admin_group(user):
    """Revoke access when account is no longer approved and active."""
    if user.pk is None:
        return
    group = Group.objects.filter(name=MEDICAL_MANAGER_GROUP).first()
    if not group:
        return
    from .access_control import is_approved_doctor
    if is_approved_doctor(user):
        user.groups.add(group)
    else:
        user.groups.remove(group)
