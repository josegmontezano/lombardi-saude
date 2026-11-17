from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies=[('clinic','0005_seed_protocols')]
    operations=[
        migrations.CreateModel(name='PortalAccount',fields=[
            ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
            ('phone',models.CharField(max_length=11,verbose_name='Celular (DDD + número)')),
            ('privacy_acknowledged_at',models.DateTimeField(verbose_name='Aviso de privacidade apresentado')),
            ('created_at',models.DateTimeField(auto_now_add=True)),
            ('updated_at',models.DateTimeField(auto_now=True)),
            ('user',models.OneToOneField(to=settings.AUTH_USER_MODEL,on_delete=django.db.models.deletion.CASCADE,related_name='portal_account')),
        ]),
        migrations.AlterField(model_name='patientprofile',name='cpf',field=models.CharField(max_length=11,unique=True,db_index=True,null=True,blank=True,verbose_name='CPF')),
        migrations.AddField(model_name='patientprofile',name='cpf_missing_reason',field=models.CharField(max_length=180,blank=True,verbose_name='Justificativa para ausência de CPF')),
        migrations.AddField(model_name='patientprofile',name='birth_record_number',field=models.CharField(max_length=40,blank=True,verbose_name='Número da Declaração de Nascido Vivo (DNV)')),
        migrations.AddField(model_name='patientprofile',name='marital_status',field=models.CharField(max_length=32,blank=True,choices=[('', 'Não informado'),('solteiro','Solteiro(a)'),('casado','Casado(a)'),('uniao_estavel','União estável'),('divorciado','Divorciado(a)'),('viuvo','Viúvo(a)'),('outro','Outro')],verbose_name='Estado civil')),
        migrations.AddField(model_name='patientprofile',name='blood_type',field=models.CharField(max_length=3,blank=True,choices=[('', 'Não informado'),('A+','A+'),('A-','A-'),('B+','B+'),('B-','B-'),('AB+','AB+'),('AB-','AB-'),('O+','O+'),('O-','O-')],verbose_name='Tipo sanguíneo (quando conhecido)')),
        migrations.AddField(model_name='patientprofile',name='ethnicity',field=models.CharField(max_length=100,blank=True,verbose_name='Etnia (quando aplicável)')),
        migrations.AddField(model_name='patientprofile',name='educational_level',field=models.CharField(max_length=32,blank=True,choices=[('','Não informado'),('sem_escolaridade','Sem escolaridade'),('fundamental_incompleto','Fundamental incompleto'),('fundamental_completo','Fundamental completo'),('medio_incompleto','Médio incompleto'),('medio_completo','Médio completo'),('superior_incompleto','Superior incompleto'),('superior_completo','Superior completo'),('pos_graduacao','Pós-graduação')],verbose_name='Escolaridade')),
        migrations.AddField(model_name='patientprofile',name='occupation',field=models.CharField(max_length=120,blank=True,verbose_name='Ocupação')),
        migrations.AddField(model_name='patientprofile',name='employment',field=models.CharField(max_length=32,blank=True,choices=[('','Não informado'),('empregado','Trabalho formal'),('informal','Trabalho informal/autônomo'),('desempregado','Desempregado'),('aposentado','Aposentado/pensionista'),('estudante','Estudante'),('nao_trabalha','Não trabalha'),('outro','Outro')],verbose_name='Situação no mercado de trabalho')),
        migrations.AddField(model_name='patientprofile',name='private_health_plan',field=models.CharField(max_length=3,blank=True,choices=[('','Não informado'),('sim','Sim'),('nao','Não')],verbose_name='Possui plano de saúde?')),
        migrations.AddField(model_name='patientprofile',name='traditional_community',field=models.CharField(max_length=100,blank=True,verbose_name='Povo/comunidade tradicional (se informado)')),
        migrations.AddField(model_name='patientprofile',name='homeless',field=models.CharField(max_length=3,blank=True,choices=[('','Não informado'),('sim','Sim'),('nao','Não')],verbose_name='Em situação de rua?')),
        migrations.AddField(model_name='patientprofile',name='disabilities',field=models.CharField(max_length=200,blank=True,help_text='Auditiva, visual, intelectual/cognitiva, física ou outra; somente com relato do paciente.',verbose_name='Deficiência autorreferida')),
        *[migrations.AddField(model_name='patientprofile',name=name,field=models.CharField(max_length=3,blank=True,choices=[('','Não informado'),('sim','Sim'),('nao','Não')],verbose_name=label)) for name,label in [
            ('hypertension','Hipertensão autorreferida'),('diabetes','Diabetes autorreferido'),('heart_disease','Doença cardíaca autorreferida'),('kidney_disease','Doença renal autorreferida'),('respiratory_disease','Doença respiratória autorreferida'),('pregnancy','Gestação autorreferida (se aplicável)'),('smoking','Tabagismo autorreferido'),
        ]],
        migrations.AddField(model_name='patientprofile',name='other_conditions',field=models.TextField(blank=True,verbose_name='Outras condições autorreferidas (informadas voluntariamente)')),
        migrations.AddField(model_name='patientprofile',name='staff_updated_by',field=models.ForeignKey(to=settings.AUTH_USER_MODEL,on_delete=django.db.models.deletion.SET_NULL,null=True,blank=True,related_name='updated_clinical_profiles')),
        migrations.AddField(model_name='patientprofile',name='verified_at',field=models.DateTimeField(blank=True,null=True,verbose_name='Ficha conferida pela equipe')),
    ]
