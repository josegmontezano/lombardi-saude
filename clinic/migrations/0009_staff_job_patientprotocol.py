# Lombardi Saúde v0.7.5 - profissionais e protocolo individualizado
import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('clinic', '0008_patientdocument_transcription'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='staff_job',
            field=models.CharField(blank=True, choices=[('', 'Permissões anteriores / não definido'), ('doctor', 'Médico'), ('nurse', 'Enfermeiro'), ('nursing_technician', 'Técnico de Enfermagem'), ('finance_unit', 'Financeiro / Administrador de Unidade'), ('reception', 'Recepção')], default='', max_length=25, verbose_name='Cargo do funcionário'),
        ),
        migrations.CreateModel(
            name='PatientProtocol',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('clinical_justification', models.TextField(verbose_name='Justificativa clínica individual')),
                ('instructions', models.TextField(blank=True, verbose_name='Orientações ao paciente')),
                ('scheduled_for', models.DateField(blank=True, null=True, verbose_name='Data programada')),
                ('status', models.CharField(choices=[('pending','A realizar'), ('performed','Realizado'), ('cancelled','Cancelado')], default='pending', max_length=12)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('patient', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='patient_protocols', to=settings.AUTH_USER_MODEL)),
                ('prescribed_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='protocol_orders_authored', to=settings.AUTH_USER_MODEL)),
                ('protocol', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='patient_orders', to='clinic.protocol')),
            ],
            options={
                'ordering':['-created_at'],
                'indexes':[models.Index(fields=['status','scheduled_for'], name='clinic_patientprotocol_qidx')],
            },
        ),
    ]
