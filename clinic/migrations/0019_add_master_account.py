from django.db import migrations

# Do not seed real login credentials from source control.
class Migration(migrations.Migration):
    dependencies = [("clinic", "0018_remove_master_privileges")]
    operations = [migrations.RunPython(migrations.RunPython.noop, migrations.RunPython.noop)]
