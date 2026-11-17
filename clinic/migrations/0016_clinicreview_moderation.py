from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [
        ("clinic", "0015_clinicreview"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.AddField(model_name="clinicreview", name="patient_name", field=models.CharField(blank=True, default="",max_length=140,verbose_name="Nome completo")),
        migrations.AddField(model_name="clinicreview", name="patient_email", field=models.EmailField(blank=True, default="",max_length=254,verbose_name="E-mail do paciente")),
        migrations.AddField(model_name="clinicreview", name="patient_phone", field=models.CharField(blank=True, default="",max_length=20,verbose_name="Telefone do paciente")),
        migrations.AddField(model_name="clinicreview", name="status", field=models.CharField(choices=[("pending","Aguardando análise"),("approved","Aprovada"),("rejected","Não aprovada")],db_index=True,default="pending",max_length=12,verbose_name="Revisão profissional")),
        migrations.AddField(model_name="clinicreview", name="reviewed_at",field=models.DateTimeField(blank=True,null=True,verbose_name="Data da revisão")),
        migrations.AddField(model_name="clinicreview", name="reviewed_by",field=models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,related_name="moderated_clinic_reviews",to=settings.AUTH_USER_MODEL,verbose_name="Profissional responsável")),
    ]
