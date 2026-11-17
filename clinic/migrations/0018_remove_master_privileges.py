from django.db import migrations

def remove_master_role(apps,schema_editor):
    User=apps.get_model("clinic","User")
    db=schema_editor.connection.alias
    # Preserve account records and password hashes for audit/continuity,
    # but revoke superuser authority; existing authorized admins remain admins.
    User.objects.using(db).filter(is_superuser=True).update(
        is_superuser=False,
        role="admin",
    )

class Migration(migrations.Migration):
    dependencies=[("clinic","0017_staffaccess_request")]
    operations=[migrations.RunPython(remove_master_role,migrations.RunPython.noop)]
