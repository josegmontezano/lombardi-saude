from django.db import migrations, models
from django.db.models import Q

class Migration(migrations.Migration):
    dependencies = [("clinic", "0014_instagramentry_visitorsubmission_websitevisit")]
    operations = [
        migrations.CreateModel(
            name="ClinicReview",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("unit", models.CharField(choices=[("campo_grande","Campo Grande/RJ"),("alegre","Alegre/ES")],db_index=True,max_length=20,verbose_name="Unidade")),
                ("reception", models.PositiveSmallIntegerField(verbose_name="Recepção (0–5)")),
                ("nursing_technician",models.PositiveSmallIntegerField(verbose_name="Técnico de Enfermagem (0–5)")),
                ("nursing",models.PositiveSmallIntegerField(verbose_name="Enfermagem (0–5)")),
                ("doctor",models.PositiveSmallIntegerField(verbose_name="Médico (0–5)")),
                ("private_comment",models.TextField(blank=True,max_length=750,verbose_name="Comentário para gestão")),
                ("created_at",models.DateTimeField(auto_now_add=True,db_index=True,verbose_name="Data")),
            ],
            options={"ordering":("-created_at",),"verbose_name":"Avaliação de atendimento","verbose_name_plural":"Avaliações de atendimento"},
        ),
        migrations.AddIndex(model_name="clinicreview", index=models.Index(fields=["unit","created_at"],name="review_unit_created_idx")),
        migrations.AddConstraint(model_name="clinicreview",constraint=models.CheckConstraint(condition=Q(reception__gte=0)&Q(reception__lte=5),name="rev_reception_0_5")),
        migrations.AddConstraint(model_name="clinicreview",constraint=models.CheckConstraint(condition=Q(nursing_technician__gte=0)&Q(nursing_technician__lte=5),name="rev_tech_0_5")),
        migrations.AddConstraint(model_name="clinicreview",constraint=models.CheckConstraint(condition=Q(nursing__gte=0)&Q(nursing__lte=5),name="rev_nurse_0_5")),
        migrations.AddConstraint(model_name="clinicreview",constraint=models.CheckConstraint(condition=Q(doctor__gte=0)&Q(doctor__lte=5),name="rev_doctor_0_5")),
    ]
