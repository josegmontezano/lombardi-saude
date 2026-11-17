"""Clinic models. All sensitive documents are private and accessed only through permission-checked views."""
import uuid
from datetime import timedelta
from django.conf import settings
from django.contrib.auth.models import AbstractUser, UserManager
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

class ClinicUserManager(UserManager):
    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("role", "admin")
        return super().create_superuser(username, email, password, **extra_fields)


class User(AbstractUser):
    PATIENT, STAFF, ADMIN = "patient", "staff", "admin"
    ROLE = [(PATIENT, "Paciente"), (STAFF, "Funcionário"), (ADMIN, "Administrador")]
    JOB_DOCTOR, JOB_NURSE, JOB_TECH, JOB_FINANCE, JOB_RECEPTION = (
        "doctor", "nurse", "nursing_technician", "finance_unit", "reception"
    )
    STAFF_JOBS = [
        ("", "Permissões anteriores / não definido"),
        (JOB_DOCTOR, "Médico"),
        (JOB_NURSE, "Enfermeiro"),
        (JOB_TECH, "Técnico de Enfermagem"),
        (JOB_FINANCE, "Financeiro / Administrador de Unidade"),
        (JOB_RECEPTION, "Recepção"),
    ]
    objects = ClinicUserManager()
    role = models.CharField("perfil", max_length=12, choices=ROLE, default=PATIENT)
    staff_job = models.CharField("Cargo do funcionário", max_length=25, choices=STAFF_JOBS, blank=True, default="")
    email = models.EmailField(unique=True)
    patient_verified = models.BooleanField("Identidade do paciente conferida", default=False)
    clinical_access = models.BooleanField("Permissão clínica", default=False)
    financial_access = models.BooleanField("Permissão financeira", default=False)
    must_change_password = models.BooleanField("Troca de senha obrigatória", default=False)

    def save(self, *args, **kwargs):
        self.email = (self.email or "").strip().lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.get_full_name() or self.username

class Service(models.Model):
    title = models.CharField("Atendimento", max_length=150)
    description = models.TextField("Descrição", blank=True)
    duration_minutes = models.PositiveIntegerField("Duração em minutos", default=45)
    active = models.BooleanField(default=True)

    def clean(self):
        if not 15 <= self.duration_minutes <= 240:
            raise ValidationError("Duração permitida: de 15 a 240 minutos.")

    def __str__(self):
        return self.title

class Slot(models.Model):
    service = models.ForeignKey(Service, on_delete=models.PROTECT, related_name="slots")
    professional = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="slots", limit_choices_to={"role__in": [User.STAFF, User.ADMIN]})
    starts_at = models.DateTimeField("Início")
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["starts_at"]
        constraints = [models.UniqueConstraint(fields=["professional", "starts_at"], name="unique_professional_start")]

    def clean(self):
        super().clean()
        if not self.professional_id or not self.service_id or not self.starts_at or not self.active:
            return
        my_start = self.starts_at
        my_end = my_start + timedelta(minutes=self.service.duration_minutes)
        potential = Slot.objects.filter(professional_id=self.professional_id, active=True, starts_at__lt=my_end, starts_at__gt=my_start - timedelta(minutes=240)).exclude(pk=self.pk).select_related("service")
        for other in potential:
            if other.starts_at + timedelta(minutes=other.service.duration_minutes) > my_start:
                raise ValidationError("Este profissional já possui horário que se sobrepõe a esse atendimento.")

    def __str__(self):
        return f"{self.service.title} · {timezone.localtime(self.starts_at):%d/%m/%Y %H:%M}"

class Appointment(models.Model):
    """Consulta confirmada diretamente, sem cobrança ou reserva provisória."""
    CONFIRMED, CANCELLED = "confirmed", "cancelled"
    STATUSES = [(CONFIRMED, "Confirmada"), (CANCELLED, "Cancelada")]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="appointments")
    slot = models.ForeignKey(Slot, on_delete=models.PROTECT, related_name="appointments")
    status = models.CharField(max_length=20, choices=STATUSES, default=CONFIRMED)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["slot"], condition=Q(status="confirmed"), name="unique_active_appointment_per_slot")]

class ExamOrder(models.Model):
    STATUSES = [("requested", "Solicitado"), ("scheduled", "Agendado"), ("performed", "Realizado"), ("result", "Resultado disponível"), ("reviewed", "Avaliado")]
    patient = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="exams", on_delete=models.PROTECT)
    title = models.CharField(max_length=180)
    instructions = models.TextField(blank=True)
    status = models.CharField(max_length=15, choices=STATUSES, default="requested")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="ordered_exams")
    created_at = models.DateTimeField(auto_now_add=True)

class ClinicalEntry(models.Model):
    patient = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="records", on_delete=models.PROTECT)
    title = models.CharField(max_length=180)
    summary = models.TextField()
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="authored_entries")
    release_to_patient = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)


def invoice_document_path(instance, filename):
    return f"legacy-nfse/{instance.patient_id}/{uuid.uuid4().hex}.pdf"

class InvoiceRequest(models.Model):
    REQUESTED, REVIEWING, NEED_DATA, DONE = "requested", "reviewing", "needs_data", "done"
    STATUSES = [(REQUESTED, "Solicitada"), (REVIEWING, "Em análise"), (NEED_DATA, "Dados pendentes"), (DONE, "Emitida")]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="invoice_requests")
    appointment = models.ForeignKey(Appointment, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=12, choices=STATUSES, default=REQUESTED)
    invoice_number = models.CharField(max_length=90, blank=True)
    document_pdf = models.BinaryField(blank=True, null=True, editable=False)
    staff_response = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    billing_snapshot = models.JSONField('Dados fiscais informados na solicitação', default=dict, blank=True, editable=False)

    @property
    def billing_data(self):
        if self.billing_snapshot:
            return self.billing_snapshot
        profile = PatientProfile.objects.filter(user_id=self.patient_id).first()
        return fiscal_data_for_patient(self.patient, profile) if profile else {"name": self.patient.get_full_name() or self.patient.email, "email": self.patient.email}

    def clean(self):
        if self.status == self.DONE and (not self.document_pdf or not self.invoice_number):
            raise ValidationError("Para marcar como emitida, informe número e arquivo PDF.")

class Notification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    category = models.CharField(max_length=40)
    title = models.CharField(max_length=180)
    message = models.TextField()
    link = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

class AuditEvent(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=80)
    subject = models.CharField(max_length=80)
    reference_id = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

class PortalAccount(models.Model):
    """Dados mínimos da conta pública. Não é cadastro clínico nem verificação de identidade."""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="portal_account")
    phone = models.CharField("Celular (DDD + número)", max_length=11)
    privacy_acknowledged_at = models.DateTimeField("Aviso de privacidade apresentado")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.user.email


class PatientProfile(models.Model):
    """Ficha interna estruturada a partir do PEC. Não sincroniza com e-SUS/CadSUS."""
    SEX = [('F', 'Feminino'), ('M', 'Masculino'), ('I', 'Intersexo/indeterminado'), ('N', 'Prefiro não informar')]
    RACE = [('branca','Branca'),('preta','Preta'),('parda','Parda'),('amarela','Amarela'),('indigena','Indígena'),('nao_informada','Prefiro não informar')]
    NATIONALITY = [('brasileira','Brasileira'),('naturalizada','Brasileira naturalizada'),('estrangeira','Estrangeira')]
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='patient_profile')
    cpf = models.CharField('CPF', max_length=11, unique=True, db_index=True, null=True, blank=True)
    cpf_missing_reason = models.CharField('Justificativa para ausência de CPF', max_length=180, blank=True)
    birth_record_number = models.CharField('Número da Declaração de Nascido Vivo (DNV)', max_length=40, blank=True)
    marital_status = models.CharField('Estado civil', max_length=32, blank=True, choices=[('', 'Não informado'), ('solteiro','Solteiro(a)'), ('casado','Casado(a)'), ('uniao_estavel','União estável'), ('divorciado','Divorciado(a)'), ('viuvo','Viúvo(a)'), ('outro','Outro')])
    blood_type = models.CharField('Tipo sanguíneo (quando conhecido)', max_length=3, blank=True, choices=[('', 'Não informado'), ('A+','A+'), ('A-','A-'), ('B+','B+'), ('B-','B-'), ('AB+','AB+'), ('AB-','AB-'), ('O+','O+'), ('O-','O-')])
    cns = models.CharField('Cartão Nacional de Saúde (CNS)', max_length=15, blank=True)
    social_name = models.CharField('Nome social', max_length=150, blank=True)
    birth_date = models.DateField('Data de nascimento')
    sex = models.CharField('Sexo cadastral', max_length=1, choices=SEX)
    race_color = models.CharField('Raça/cor autodeclarada', max_length=14, choices=RACE)
    mother_name = models.CharField('Nome da mãe', max_length=150, blank=True)
    mother_unknown = models.BooleanField('Nome da mãe desconhecido', default=False)
    father_name = models.CharField('Nome do pai', max_length=150, blank=True)
    nationality = models.CharField('Nacionalidade', max_length=12, choices=NATIONALITY, default='brasileira')
    birth_city = models.CharField('Município de nascimento', max_length=100, blank=True)
    birth_state = models.CharField('UF de nascimento', max_length=2, blank=True)
    birth_country = models.CharField('País de nascimento', max_length=70, default='Brasil')
    phone = models.CharField('Celular (com DDD)', max_length=15)
    phone_alt = models.CharField('Telefone alternativo', max_length=15, blank=True)
    postal_code = models.CharField('CEP', max_length=8)
    address_street = models.CharField('Logradouro', max_length=180)
    address_number = models.CharField('Número', max_length=20)
    address_complement = models.CharField('Complemento', max_length=120, blank=True)
    address_neighborhood = models.CharField('Bairro', max_length=100)
    address_city = models.CharField('Cidade', max_length=100)
    address_state = models.CharField('UF', max_length=2)
    emergency_name = models.CharField('Contato de emergência', max_length=150, blank=True)
    emergency_phone = models.CharField('Telefone de emergência', max_length=15, blank=True)
    guardian_name = models.CharField('Nome do responsável legal (menores)', max_length=150, blank=True)
    guardian_phone = models.CharField('Contato do responsável legal', max_length=15, blank=True)
    EDUCATION = [('','Não informado'),('sem_escolaridade','Sem escolaridade'),('fundamental_incompleto','Fundamental incompleto'),('fundamental_completo','Fundamental completo'),('medio_incompleto','Médio incompleto'),('medio_completo','Médio completo'),('superior_incompleto','Superior incompleto'),('superior_completo','Superior completo'),('pos_graduacao','Pós-graduação')]
    EMPLOYMENT = [('','Não informado'),('empregado','Trabalho formal'),('informal','Trabalho informal/autônomo'),('desempregado','Desempregado'),('aposentado','Aposentado/pensionista'),('estudante','Estudante'),('nao_trabalha','Não trabalha'),('outro','Outro')]
    ANSWER = [('','Não informado'),('sim','Sim'),('nao','Não')]
    ethnicity = models.CharField('Etnia (quando aplicável)', max_length=100, blank=True)
    educational_level = models.CharField('Escolaridade', max_length=32, blank=True, choices=EDUCATION)
    occupation = models.CharField('Ocupação', max_length=120, blank=True)
    employment = models.CharField('Situação no mercado de trabalho', max_length=32, blank=True, choices=EMPLOYMENT)
    private_health_plan = models.CharField('Possui plano de saúde?', max_length=3, blank=True, choices=ANSWER)
    traditional_community = models.CharField('Povo/comunidade tradicional (se informado)', max_length=100, blank=True)
    homeless = models.CharField('Em situação de rua?', max_length=3, blank=True, choices=ANSWER)
    disabilities = models.CharField('Deficiência autorreferida', max_length=200, blank=True, help_text='Auditiva, visual, intelectual/cognitiva, física ou outra; somente com relato do paciente.')
    hypertension = models.CharField('Hipertensão autorreferida', max_length=3, blank=True, choices=ANSWER)
    diabetes = models.CharField('Diabetes autorreferido', max_length=3, blank=True, choices=ANSWER)
    heart_disease = models.CharField('Doença cardíaca autorreferida', max_length=3, blank=True, choices=ANSWER)
    kidney_disease = models.CharField('Doença renal autorreferida', max_length=3, blank=True, choices=ANSWER)
    respiratory_disease = models.CharField('Doença respiratória autorreferida', max_length=3, blank=True, choices=ANSWER)
    pregnancy = models.CharField('Gestação autorreferida (se aplicável)', max_length=3, blank=True, choices=ANSWER)
    smoking = models.CharField('Tabagismo autorreferido', max_length=3, blank=True, choices=ANSWER)
    other_conditions = models.TextField('Outras condições autorreferidas (informadas voluntariamente)', blank=True)
    staff_updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='updated_clinical_profiles')
    verified_at = models.DateTimeField('Ficha conferida pela equipe', null=True, blank=True)
    registration_completed_at = models.DateTimeField('Cadastro completo pelo paciente', null=True, blank=True)
    privacy_acknowledged_at = models.DateTimeField('Aviso de privacidade apresentado', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def masked_cpf(self):
        return '***.***.***-' + self.cpf[-2:] if self.cpf else '—'

    def __str__(self):
        return f'{self.user.get_full_name() or self.user.username} · {self.masked_cpf}'


class Protocol(models.Model):
    """Informational clinical catalogue, not a prescription or medical order."""
    MEDICATION, NUTRIENT, NUTRACEUTICAL, COMPOUND, CARE = 'medicamento','nutriente','nutraceutico','formula','cuidado'
    CATEGORIES = [(MEDICATION,'Medicamento'),(NUTRIENT,'Vitaminas e minerais'),(NUTRACEUTICAL,'Ativos e nutracêuticos'),(COMPOUND,'Fórmulas e associações'),(CARE,'Protocolo de cuidado')]
    name = models.CharField(max_length=150, unique=True)
    category = models.CharField(max_length=15, choices=CATEGORIES)
    description = models.CharField(max_length=480)
    supplier_reference = models.CharField(max_length=180, blank=True)
    prescription_required = models.BooleanField(default=True)
    medically_reviewed = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('sort_order','name')

    def __str__(self):
        return self.name

class LoginAttempt(models.Model):
    identifier = models.CharField(max_length=64, unique=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    window_started_at = models.DateTimeField(default=timezone.now)
    locked_until = models.DateTimeField(null=True, blank=True)


class PatientDocument(models.Model):
    """PDF privado de receita ou plano alimentar; NFS-e permanece em InvoiceRequest.

    Somente o titular com identidade validada e a equipe clínica autorizada podem
    obter o conteúdo. PDF em PostgreSQL para persistência no ambiente serverless.
    """
    PRESCRIPTION, DIET = "prescription", "diet"
    KINDS = [(PRESCRIPTION, "Receita"), (DIET, "Dieta")]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="patient_documents")
    kind = models.CharField(max_length=20, choices=KINDS)
    title = models.CharField(max_length=160)
    document_pdf = models.BinaryField(editable=False)
    transcription = models.TextField("Transcrição para consulta na tela", blank=True, default="", max_length=12000)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="uploaded_patient_documents")
    created_at = models.DateTimeField(auto_now_add=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["patient", "kind", "active", "created_at"], name="clinic_doc_patient_kind_idx")]

    def clean(self):
        super().clean()
        blob = bytes(self.document_pdf or b"")
        if not blob.startswith(b"%PDF-") or len(blob) > 5 * 1024 * 1024 or len(blob) < 8:
            raise ValidationError("É necessário fornecer PDF válido de até 5 MB.")
        if self.patient_id and self.patient.role != User.PATIENT:
            raise ValidationError("Este arquivo só pode ser atribuído a um paciente.")


class PatientProtocol(models.Model):
    """Clinical order by an authorized physician, never created automatically."""
    PENDING, PERFORMED, CANCELLED = 'pending', 'performed', 'cancelled'
    STATUSES = [(PENDING, 'A realizar'), (PERFORMED, 'Realizado'), (CANCELLED, 'Cancelado')]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='patient_protocols')
    protocol = models.ForeignKey(Protocol, on_delete=models.PROTECT, related_name='patient_orders')
    prescribed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='protocol_orders_authored')
    clinical_justification = models.TextField('Justificativa clínica individual')
    instructions = models.TextField('Orientações ao paciente', blank=True)
    scheduled_for = models.DateField('Data programada', blank=True, null=True)
    status = models.CharField(max_length=12, choices=STATUSES, default=PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['status','scheduled_for'], name='clinic_patientprotocol_qidx')]

    def clean(self):
        if not self.clinical_justification or not self.clinical_justification.strip():
            raise ValidationError('A indicação requer justificativa individual documentada.')
        if self.prescribed_by_id and not (self.prescribed_by.role == User.STAFF and self.prescribed_by.staff_job == User.JOB_DOCTOR):
            raise ValidationError('A indicação de protocolos é exclusiva do perfil médico.')
        if self.patient_id and self.patient.role != User.PATIENT:
            raise ValidationError('É necessário selecionar um paciente.')


def fiscal_data_for_patient(patient, profile):
    """Dados mínimos para emissão, sem incluir informações médicas."""
    return {
        'name': patient.get_full_name() or patient.email,
        'cpf': profile.cpf or '',
        'email': patient.email,
        'phone': profile.phone,
        'postal_code': profile.postal_code,
        'address_street': profile.address_street,
        'address_number': profile.address_number,
        'address_complement': profile.address_complement,
        'address_neighborhood': profile.address_neighborhood,
        'address_city': profile.address_city,
        'address_state': profile.address_state,
    }


class VlogVideo(models.Model):
    """Public educational posts managed in Django administration; no personal health data."""
    CATEGORIES = [
        ('prevencao', 'Prevenção e saúde'),
        ('metabolismo', 'Metabolismo e peso'),
        ('nutricao', 'Nutrição e hábitos'),
        ('bem-estar', 'Qualidade de vida'),
        ('duvidas', 'Dúvidas frequentes'),
        ('institucional', 'Institucional'),
    ]
    title = models.CharField('Título do vídeo', max_length=180)
    slug = models.SlugField('Endereço da publicação', max_length=180, unique=True)
    category = models.CharField('Categoria', max_length=30, choices=CATEGORIES, default='prevencao')
    summary = models.TextField('Resumo para a lista de publicações', blank=True)
    video_url = models.URLField('Link externo de vídeo (opcional)', max_length=500, blank=True)
    body = models.TextField('Texto da reportagem / artigo (sem limite editorial)', blank=True)
    cover_url = models.URLField('URL da capa no armazenamento Vercel', max_length=900, blank=True)
    media_url = models.URLField('URL de vídeo armazenado na Vercel', max_length=900, blank=True)
    private_media_path = models.CharField('Caminho privado do vídeo', max_length=280, blank=True, default='')
    publish_at = models.DateTimeField('Publicado a partir de', default=timezone.now)
    published = models.BooleanField('Visível no site', default=True)
    featured = models.BooleanField('Destaque', default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-publish_at', '-created_at')
        verbose_name = 'Vídeo do Vlog'
        verbose_name_plural = 'Vídeos do Vlog'

    def __str__(self):
        return self.title

    @property
    def embed_url(self):
        """Returns only validated, fixed-format embed URLs, never user-provided HTML."""
        import re
        from urllib.parse import urlsplit, parse_qs
        u = urlsplit(self.video_url)
        host = (u.hostname or '').lower()
        if u.scheme != 'https' or u.username or u.password or u.port:
            return ''
        parts = [x for x in u.path.split('/') if x]
        video_id = ''
        if host in ('youtube.com', 'www.youtube.com', 'm.youtube.com', 'youtube-nocookie.com', 'www.youtube-nocookie.com'):
            if u.path == '/watch': video_id = parse_qs(u.query).get('v', [''])[0]
            elif len(parts) == 2 and parts[0] in ('shorts', 'embed', 'live'): video_id = parts[1]
            if re.fullmatch(r'[A-Za-z0-9_-]{11}', video_id):
                return 'https://www.youtube-nocookie.com/embed/' + video_id
        if host == 'youtu.be' and len(parts) == 1 and re.fullmatch(r'[A-Za-z0-9_-]{11}', parts[0]):
            return 'https://www.youtube-nocookie.com/embed/' + parts[0]
        if host in ('vimeo.com', 'www.vimeo.com', 'player.vimeo.com'):
            if len(parts) == 1:video_id=parts[0]
            elif len(parts) == 2 and parts[0] == 'video': video_id=parts[1]
            if re.fullmatch(r'[0-9]{6,12}', video_id):
                return 'https://player.vimeo.com/video/' + video_id
        return ''

    def clean(self):
        super().clean()
        from urllib.parse import urlsplit
        u = urlsplit(self.video_url or '')
        if not self.video_url:
            if not self.body.strip() and not self.media_url and not self.private_media_path:
                raise ValidationError('Informe texto ou vídeo para publicar.')
        if self.video_url and (u.scheme != 'https' or u.username or u.password or u.port):
            raise ValidationError({'video_url':'Use um endereço HTTPS válido de YouTube, Vimeo ou Instagram.'})
        host = (u.hostname or '').lower()
        allowed = ('youtube.com','www.youtube.com','m.youtube.com', 'youtube-nocookie.com',
                   'www.youtube-nocookie.com','youtu.be','vimeo.com','www.vimeo.com',
                   'player.vimeo.com','instagram.com','www.instagram.com')
        if self.video_url and host not in allowed:
            raise ValidationError({'video_url':'Apenas links do YouTube, Vimeo ou Instagram são permitidos.'})
        if self.video_url and 'instagram.com' in host:
            if not any(u.path.startswith('/' + name + '/') for name in ('reel','reels','p','tv')):
                raise ValidationError({'video_url':'Informe o link de um vídeo ou Reel do Instagram.'})
        elif self.video_url and not self.embed_url:
            raise ValidationError({'video_url':'Informe o link válido de um vídeo público.'})

        import re
        if self.private_media_path and not re.fullmatch(r'vlog/private/[0-9]{1,12}/[0-9a-f]{32}\.(?:mp4|webm|mov)', self.private_media_path):
            raise ValidationError({'private_media_path':'Caminho privado inválido.'})
        from urllib.parse import urlsplit
        for field in ('media_url', 'cover_url'):
            value = getattr(self, field, '') or ''
            if value:
                parsed = urlsplit(value)
                if parsed.scheme != 'https' or parsed.username or parsed.password or not (parsed.hostname or '').endswith('.public.blob.vercel-storage.com') or '/vlog/' not in parsed.path:
                    raise ValidationError({field:'Somente mídia enviada ao armazenamento de Vlog da Lombardi Saúde é permitida.'})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class WebsiteVisit(models.Model):
    """Opt-in analytics: no IP, email or user-agent stored."""
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    page_path = models.CharField(max_length=240)
    visitor_token = models.CharField(max_length=64, blank=True, db_index=True)
    country = models.CharField(max_length=3, blank=True, default='')
    region = models.CharField(max_length=6, blank=True, default='')
    city = models.CharField(max_length=100, blank=True, default='')

    class Meta:
        indexes = [models.Index(fields=['created_at','country'], name='lx_visit_geo_date')]
        ordering = ('-created_at',)
        verbose_name = 'Acesso do site (com consentimento)'
        verbose_name_plural = 'Acessos do site (com consentimento)'


class VisitorSubmission(models.Model):
    KINDS = [('question','Dúvida para a Lombardi Saúde'), ('message','Mensagem para publicação')]
    STATUSES = [('pending','Aguardando análise'),('answered','Respondida (privada)'),
                ('published','Publicada'),('rejected','Não aprovada')]
    kind = models.CharField('Tipo', max_length=12, choices=KINDS)
    name = models.CharField('Nome (interno)', max_length=100)
    email = models.EmailField('E-mail (interno)')
    text = models.TextField('Mensagem ou dúvida', max_length=5000)
    publish_authorized = models.BooleanField('Autorizou publicação pública', default=False)
    show_name = models.BooleanField('Autorizou divulgar primeiro nome', default=False)
    privacy_ack = models.BooleanField('Confirmou aviso de privacidade', default=False)
    homepage = models.CharField('Campo antispam', max_length=160, blank=True)
    status = models.CharField('Situação', max_length=12, choices=STATUSES, default='pending')
    answer = models.TextField('Resposta oficial da Lombardi Saúde', blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def public_author(self):
        return self.name.split()[0] if self.show_name and self.publish_authorized else 'Participante'

    def clean(self):
        super().clean()
        from django.core.exceptions import ValidationError
        if self.status == 'published' and not self.publish_authorized:
            raise ValidationError('A mensagem só pode ser publicada com autorização explícita.')
        if self.status == 'published' and self.kind == 'question' and not self.answer.strip():
            raise ValidationError('Uma dúvida só pode ser publicada quando for respondida.')
        if self.show_name and not self.publish_authorized:
            raise ValidationError('O nome só pode ser divulgado com autorização de publicação.')

    class Meta:
        ordering = ('-created_at',)
        verbose_name = 'Mensagem / dúvida do público'
        verbose_name_plural = 'Mensagens / dúvidas do público'


class InstagramEntry(models.Model):
    TYPES = [('IMAGE','Imagem'),('VIDEO','Vídeo'),('CAROUSEL_ALBUM','Carrossel'),('STORY','Story')]
    instagram_id = models.CharField('ID oficial do Instagram', max_length=90, unique=True)
    kind = models.CharField('Tipo de mídia', max_length=20, choices=TYPES)
    caption = models.TextField('Legenda', blank=True)
    permalink = models.URLField('Link oficial', max_length=700)
    media_url = models.URLField('Mídia oficial', max_length=950, blank=True)
    thumbnail_url = models.URLField('Miniatura', max_length=950, blank=True)
    posted_at = models.DateTimeField('Publicado no Instagram', db_index=True)
    expires_at = models.DateTimeField('Expira em', null=True, blank=True)
    synced_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-posted_at',)
        verbose_name = 'Conteúdo do Instagram oficial'
        verbose_name_plural = 'Conteúdos do Instagram oficial'

class ClinicReview(models.Model):
    """Patient-identified assessment, with professional moderation before public release."""
    CAMPO_GRANDE = "campo_grande"
    ALEGRE = "alegre"
    UNITS = [(CAMPO_GRANDE, "Campo Grande/RJ"), (ALEGRE, "Alegre/ES")]
    unit = models.CharField("Unidade", max_length=20, choices=UNITS, db_index=True)
    # Defaults protect previously submitted evaluations during a non-destructive migration.
    patient_name = models.CharField("Nome completo", max_length=140, blank=True, default="")
    patient_email = models.EmailField("E-mail do paciente", blank=True, default="")
    patient_phone = models.CharField("Telefone do paciente", max_length=20, blank=True, default="")
    PENDING, APPROVED, REJECTED = "pending", "approved", "rejected"
    STATUSES = [(PENDING, "Aguardando análise"), (APPROVED, "Aprovada"), (REJECTED, "Não aprovada")]
    status = models.CharField("Revisão profissional", max_length=12, choices=STATUSES, default=PENDING, db_index=True)
    reviewed_at = models.DateTimeField("Data da revisão", null=True, blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="Profissional responsável", on_delete=models.SET_NULL, null=True, blank=True, related_name="moderated_clinic_reviews")
    reception = models.PositiveSmallIntegerField("Recepção (0–5)")
    nursing_technician = models.PositiveSmallIntegerField("Técnico de Enfermagem (0–5)")
    nursing = models.PositiveSmallIntegerField("Enfermagem (0–5)")
    doctor = models.PositiveSmallIntegerField("Médico (0–5)")
    private_comment = models.TextField("Comentário para gestão", max_length=750, blank=True)
    created_at = models.DateTimeField("Data", auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["unit", "created_at"], name="review_unit_created_idx")]
        constraints = [
            models.CheckConstraint(condition=Q(reception__gte=0) & Q(reception__lte=5), name="rev_reception_0_5"),
            models.CheckConstraint(condition=Q(nursing_technician__gte=0) & Q(nursing_technician__lte=5), name="rev_tech_0_5"),
            models.CheckConstraint(condition=Q(nursing__gte=0) & Q(nursing__lte=5), name="rev_nurse_0_5"),
            models.CheckConstraint(condition=Q(doctor__gte=0) & Q(doctor__lte=5), name="rev_doctor_0_5"),
        ]
        verbose_name = "Avaliação de atendimento"
        verbose_name_plural = "Avaliações de atendimento"

    @property
    def average(self):
        return round((self.reception + self.nursing_technician + self.nursing + self.doctor) / 4, 2)

class StaffAccessRequest(models.Model):
    PENDING, APPROVED, REJECTED = "pending", "approved", "rejected"
    STATUSES = [(PENDING, "Pendente"), (APPROVED, "Aprovada"), (REJECTED, "Recusada")]
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                related_name="staff_access_request")
    requested_job = models.CharField("Função solicitada", max_length=25, choices=User.STAFF_JOBS)
    status = models.CharField("Situação", max_length=12, choices=STATUSES, default=PENDING, db_index=True)
    created_at = models.DateTimeField("Solicitada em", auto_now_add=True)
    reviewed_at = models.DateTimeField("Analisada em", null=True, blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                    related_name="staff_access_requests_reviewed",
                                    null=True, blank=True)
    class Meta:
        ordering = ("-created_at",)
        verbose_name = "Solicitação de acesso profissional"
        verbose_name_plural = "Solicitações de acesso profissional"
