from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('clinic', '0007_patientdocument')]

    operations = [
        migrations.AddField(
            model_name='patientdocument',
            name='transcription',
            field=models.TextField(blank=True, default='', max_length=12000, verbose_name='Transcrição para consulta na tela'),
        ),
    ]
