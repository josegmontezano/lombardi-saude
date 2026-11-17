from django.apps import AppConfig
from django.db.models.signals import post_migrate, post_save


class ClinicConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "clinic"
    verbose_name = "Lombardi Saúde"

    def ready(self):
        from django.conf import settings
        from .doctor_admin_permissions import ensure_medical_admin_group, sync_medical_admin_group

        def post_migration(sender, using, **kwargs):
            ensure_medical_admin_group(using=using)

        def user_changed(sender, instance, raw, **kwargs):
            if not raw:
                sync_medical_admin_group(instance)

        post_migrate.connect(post_migration, sender=self, dispatch_uid="clinic_doctor_admin_group_ready", weak=False)
        post_save.connect(user_changed, sender=settings.AUTH_USER_MODEL, dispatch_uid="clinic_doctor_admin_group_membership", weak=False)
