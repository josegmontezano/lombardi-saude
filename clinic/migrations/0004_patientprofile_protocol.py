from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [('clinic','0003_alter_user_email_alter_user_is_active')]
    operations = [
        migrations.AddField(model_name='user',name='must_change_password',field=models.BooleanField(default=False,verbose_name='Troca de senha obrigatória')),
        migrations.CreateModel(name='LoginAttempt',fields=[
            ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
            ('identifier',models.CharField(max_length=64,unique=True)),
            ('attempts',models.PositiveSmallIntegerField(default=0)),
            ('window_started_at',models.DateTimeField(default=django.utils.timezone.now)),
            ('locked_until',models.DateTimeField(null=True,blank=True)),
        ]),
        migrations.CreateModel(name='PatientProfile',fields=[
            ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
            ('cpf',models.CharField(max_length=11,unique=True,db_index=True,verbose_name='CPF')),
            ('cns',models.CharField(max_length=15,blank=True,verbose_name='Cartão Nacional de Saúde (CNS)')),
            ('social_name',models.CharField(max_length=150,blank=True,verbose_name='Nome social')),
            ('birth_date',models.DateField(verbose_name='Data de nascimento')),
            ('sex',models.CharField(max_length=1,choices=[('F','Feminino'),('M','Masculino'),('I','Intersexo/indeterminado'),('N','Prefiro não informar')],verbose_name='Sexo cadastral')),
            ('race_color',models.CharField(max_length=14,choices=[('branca','Branca'),('preta','Preta'),('parda','Parda'),('amarela','Amarela'),('indigena','Indígena'),('nao_informada','Prefiro não informar')],verbose_name='Raça/cor autodeclarada')),
            ('mother_name',models.CharField(max_length=150,blank=True,verbose_name='Nome da mãe')),
            ('mother_unknown',models.BooleanField(default=False,verbose_name='Nome da mãe desconhecido')),
            ('father_name',models.CharField(max_length=150,blank=True,verbose_name='Nome do pai')),
            ('nationality',models.CharField(max_length=12,choices=[('brasileira','Brasileira'),('naturalizada','Brasileira naturalizada'),('estrangeira','Estrangeira')],default='brasileira',verbose_name='Nacionalidade')),
            ('birth_city',models.CharField(max_length=100,blank=True,verbose_name='Município de nascimento')),
            ('birth_state',models.CharField(max_length=2,blank=True,verbose_name='UF de nascimento')),
            ('birth_country',models.CharField(max_length=70,default='Brasil',verbose_name='País de nascimento')),
            ('phone',models.CharField(max_length=15,verbose_name='Celular (com DDD)')),
            ('phone_alt',models.CharField(max_length=15,blank=True,verbose_name='Telefone alternativo')),
            ('postal_code',models.CharField(max_length=8,verbose_name='CEP')),
            ('address_street',models.CharField(max_length=180,verbose_name='Logradouro')),
            ('address_number',models.CharField(max_length=20,verbose_name='Número')),
            ('address_complement',models.CharField(max_length=120,blank=True,verbose_name='Complemento')),
            ('address_neighborhood',models.CharField(max_length=100,verbose_name='Bairro')),
            ('address_city',models.CharField(max_length=100,verbose_name='Cidade')),
            ('address_state',models.CharField(max_length=2,verbose_name='UF')),
            ('emergency_name',models.CharField(max_length=150,blank=True,verbose_name='Contato de emergência')),
            ('emergency_phone',models.CharField(max_length=15,blank=True,verbose_name='Telefone de emergência')),
            ('guardian_name',models.CharField(max_length=150,blank=True,verbose_name='Nome do responsável legal (menores)')),
            ('guardian_phone',models.CharField(max_length=15,blank=True,verbose_name='Contato do responsável legal')),
            ('privacy_acknowledged_at',models.DateTimeField(blank=True,null=True,verbose_name='Aviso de privacidade apresentado')),
            ('created_at',models.DateTimeField(auto_now_add=True)),
            ('updated_at',models.DateTimeField(auto_now=True)),
            ('user',models.OneToOneField(to=settings.AUTH_USER_MODEL,on_delete=django.db.models.deletion.CASCADE,related_name='patient_profile')),
        ]),
        migrations.CreateModel(name='Protocol',fields=[
            ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
            ('name',models.CharField(max_length=150,unique=True)),
            ('category',models.CharField(max_length=15,choices=[('medicamento','Medicamento'),('nutriente','Vitaminas e minerais'),('nutraceutico','Ativos e nutracêuticos'),('formula','Fórmulas e associações'),('cuidado','Protocolo de cuidado')])),
            ('description',models.CharField(max_length=480)),
            ('supplier_reference',models.CharField(max_length=180,blank=True)),
            ('prescription_required',models.BooleanField(default=True)),
            ('medically_reviewed',models.BooleanField(default=False)),
            ('active',models.BooleanField(default=True)),
            ('sort_order',models.PositiveSmallIntegerField(default=0)),
            ('updated_at',models.DateTimeField(auto_now=True)),
        ], options={'ordering':('sort_order','name')}),
    ]
