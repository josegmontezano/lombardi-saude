"""Explicit and consistent access control for Lombardi clinic management."""
from .models import User


def is_approved_doctor(user):
    """Only activated doctors with an explicitly approved professional role."""
    return bool(
        user.is_authenticated
        and user.is_active
        and user.role == User.STAFF
        and user.staff_job == User.JOB_DOCTOR
        and user.is_staff
    )


def can_manage_clinic(user):
    """Master-level clinic workflow for administrators and approved doctors."""
    return bool(
        user.is_authenticated
        and user.is_active
        and (user.role == User.ADMIN or is_approved_doctor(user))
    )
