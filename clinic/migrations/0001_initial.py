# Initial schema for the independent Django/PostgreSQL deployment.
import uuid
import django.contrib.auth.models
import django.contrib.auth.validators
import django.core.validators
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models
from clinic.models import invoice_document_path, ClinicUserManager

class Migration(migrations.Migration):
    initial = True
    dependencies = [("auth", "0012_alter_user_first_name_max_length")]
    operations = [
        migrations.CreateModel(name="User", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("password", models.CharField(max_length=128, verbose_name="password")),
            ("last_login", models.DateTimeField(blank=True, null=True, verbose_name="last login")),
            ("is_superuser", models.BooleanField(default=False, help_text="Designates that this user has all permissions without explicitly assigning them.", verbose_name="superuser status")),
            ("username", models.CharField(error_messages={"unique": "A user with that username already exists."}, help_text="Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.", max_length=150, unique=True, validators=[django.contrib.auth.validators.UnicodeUsernameValidator()], verbose_name="username")),
            ("first_name", models.CharField(blank=True, max_length=150, verbose_name="first name")),
            ("last_name", models.CharField(blank=True, max_length=150, verbose_name="last name")),
            ("email", models.EmailField(max_length=254, unique=True, verbose_name="email address")),
            ("is_staff", models.BooleanField(default=False, help_text="Designates whether the user can log into this admin site.", verbose_name="staff status")),
            ("is_active", models.BooleanField(default=True, help_text="Designates whether this user should be treated as active.", verbose_name="active")),
            ("date_joined", models.DateTimeField(default=django.utils.timezone.now, verbose_name="date joined")),
            ("role", models.CharField(choices=[("patient","Paciente"),("staff","Funcionário"),("admin","Administrador")], default="patient", max_length=12, verbose_name="perfil")),
            ("patient_verified", models.BooleanField(default=False, verbose_name="Identidade do paciente conferida")),
            ("clinical_access", models.BooleanField(default=False, verbose_name="Permissão clínica")),
            ("financial_access", models.BooleanField(default=False, verbose_name="Permissão financeira")),
            ("groups", models.ManyToManyField(blank=True, help_text="The groups this user belongs to. A user will get all permissions granted to each of their groups.", related_name="user_set", related_query_name="user", to="auth.group", verbose_name="groups")),
            ("user_permissions", models.ManyToManyField(blank=True, help_text="Specific permissions for this user.", related_name="user_set", related_query_name="user", to="auth.permission", verbose_name="user permissions")),
        ], options={"verbose_name": "user", "verbose_name_plural": "users", "abstract": False}, managers=[("objects", ClinicUserManager())]),
        migrations.CreateModel(name="Service", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("title", models.CharField(max_length=150, verbose_name="Atendimento")),
            ("description", models.TextField(blank=True, verbose_name="Descrição")),
            ("duration_minutes", models.PositiveIntegerField(default=45, verbose_name="Duração em minutos")),
            ("deposit_cents", models.PositiveIntegerField(validators=[django.core.validators.MinValueValidator(100)], verbose_name="Sinal em centavos")),
            ("active", models.BooleanField(default=True)),
        ]),
        migrations.CreateModel(name="Slot", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("starts_at", models.DateTimeField(verbose_name="Início")),
            ("active", models.BooleanField(default=True)),
            ("professional", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="slots", to=settings.AUTH_USER_MODEL, limit_choices_to={"role__in": ["staff", "admin"]})),
            ("service", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="slots", to="clinic.service")),
        ], options={"ordering": ["starts_at"]}),
        migrations.AddConstraint(model_name="slot", constraint=models.UniqueConstraint(fields=("professional", "starts_at"), name="unique_professional_start")),
        migrations.CreateModel(name="Appointment", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ("status", models.CharField(choices=[("hold","Aguardando sinal"),("confirmed","Confirmada"),("expired","Prazo encerrado"),("cancelled","Cancelada"),("payment_review","Pagamento em análise")],default="hold",max_length=20)),
            ("amount_cents", models.PositiveIntegerField(validators=[django.core.validators.MinValueValidator(100)])),
            ("hold_expires_at", models.DateTimeField()),
            ("checkout_url", models.URLField(blank=True, max_length=1800)),
            ("payment_preference_id", models.CharField(blank=True, max_length=120)),
            ("payment_id", models.CharField(blank=True, max_length=120, null=True, unique=True)),
            ("paid_at", models.DateTimeField(blank=True, null=True)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("updated_at", models.DateTimeField(auto_now=True)),
            ("patient", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="appointments", to=settings.AUTH_USER_MODEL)),
            ("slot", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="appointments", to="clinic.slot")),
        ], options={"ordering": ["-created_at"]}),
        migrations.AddConstraint(model_name="appointment", constraint=models.UniqueConstraint(condition=models.Q(("status__in", ["hold", "confirmed"])), fields=("slot",), name="unique_active_appointment_per_slot")),
        migrations.CreateModel(name="ExamOrder", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("title", models.CharField(max_length=180)),
            ("instructions", models.TextField(blank=True)),
            ("status", models.CharField(choices=[("requested","Solicitado"),("scheduled","Agendado"),("performed","Realizado"),("result","Resultado disponível"),("reviewed","Avaliado")],default="requested",max_length=15)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("author", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="ordered_exams", to=settings.AUTH_USER_MODEL)),
            ("patient", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="exams", to=settings.AUTH_USER_MODEL)),
        ]),
        migrations.CreateModel(name="ClinicalEntry", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("title", models.CharField(max_length=180)),
            ("summary", models.TextField()),
            ("release_to_patient", models.BooleanField(default=False)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("author", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="authored_entries", to=settings.AUTH_USER_MODEL)),
            ("patient", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="records", to=settings.AUTH_USER_MODEL)),
        ]),
        migrations.CreateModel(name="InvoiceRequest", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ("status", models.CharField(choices=[("requested","Solicitada"),("reviewing","Em análise"),("needs_data","Dados pendentes"),("done","Emitida")],default="requested",max_length=12)),
            ("invoice_number", models.CharField(blank=True, max_length=90)),
            ("document", models.FileField(blank=True,upload_to=invoice_document_path,validators=[django.core.validators.FileExtensionValidator(["pdf"])])),
            ("staff_response", models.TextField(blank=True)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("updated_at", models.DateTimeField(auto_now=True)),
            ("appointment", models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,to="clinic.appointment")),
            ("patient", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="invoice_requests", to=settings.AUTH_USER_MODEL)),
        ]),
        migrations.CreateModel(name="Notification", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ("category", models.CharField(max_length=40)),
            ("title", models.CharField(max_length=180)),
            ("message", models.TextField()),
            ("link", models.CharField(blank=True, max_length=300)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("read_at", models.DateTimeField(blank=True, null=True)),
            ("recipient", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="notifications", to=settings.AUTH_USER_MODEL)),
        ], options={"ordering": ["-created_at"]}),
        migrations.CreateModel(name="AuditEvent", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("action", models.CharField(max_length=80)),
            ("subject", models.CharField(max_length=80)),
            ("reference_id", models.CharField(blank=True, max_length=80)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("actor", models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,to=settings.AUTH_USER_MODEL)),
        ], options={"ordering": ["-created_at"]}),
    ]
