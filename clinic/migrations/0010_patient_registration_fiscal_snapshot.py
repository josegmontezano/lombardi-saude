# Lombardi Saúde: cadastro individual completo e dados fiscais vinculados à solicitação.
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('clinic', '0009_staff_job_patientprotocol')]
    operations = [
        migrations.AddField(
            model_name='patientprofile',
            name='registration_completed_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Cadastro completo pelo paciente'),
        ),
        migrations.AddField(
            model_name='invoicerequest',
            name='billing_snapshot',
            field=models.JSONField(blank=True, default=dict, editable=False,
                                   verbose_name='Dados fiscais informados na solicitação'),
        ),
    ]
