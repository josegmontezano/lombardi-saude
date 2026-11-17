from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from .models import PatientProtocol, Protocol
from django.core.validators import validate_email
from .models import InvoiceRequest, ExamOrder, ClinicalEntry, PatientProfile, PortalAccount

User = get_user_model()

from datetime import date
import re


def only_digits(value):
    return re.sub(r"\D", "", str(value or ""))


def cpf_valid(value):
    d = only_digits(value)
    if len(d) != 11 or len(set(d)) == 1:
        return False
    for n in (9, 10):
        total = sum(int(v) * (n + 1 - i) for i, v in enumerate(d[:n]))
        check = (total * 10) % 11
        if check == 10:
            check = 0
        if check != int(d[n]):
            return False
    return True


class PatientRegisterForm(forms.Form):
    """Cadastro público de site: sem CPF, CNS ou perguntas clínicas."""
    name = forms.CharField(label='Nome completo', min_length=3, max_length=150,
                           widget=forms.TextInput(attrs={'autocomplete':'name'}))
    email = forms.EmailField(label='E-mail', widget=forms.EmailInput(attrs={'autocomplete':'email'}))
    phone = forms.CharField(label='Celular com DDD', max_length=18,
                            widget=forms.TextInput(attrs={'autocomplete':'tel','inputmode':'tel','placeholder':'(XX) XXXXX-XXXX'}))
    password = forms.CharField(label='Crie uma senha (mínimo 12 caracteres)', min_length=12, max_length=128,
                               widget=forms.PasswordInput(attrs={'autocomplete':'new-password'}))
    password_confirm = forms.CharField(label='Repita a senha',widget=forms.PasswordInput(attrs={'autocomplete':'new-password'}))
    privacy_acknowledgement = forms.BooleanField(label='Li o aviso de privacidade do portal e estou ciente do tratamento dos meus dados para manter minha conta.')

    def clean_email(self):
        email=self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError('Não foi possível criar a conta com esse e-mail.')
        return email

    def clean_phone(self):
        phone=only_digits(self.cleaned_data['phone'])
        if len(phone) != 11:
            raise ValidationError('Informe o celular com DDD (11 dígitos).')
        return phone

    def clean(self):
        data=super().clean()
        if data.get('password') and data.get('password_confirm') and data['password']!=data['password_confirm']:
            self.add_error('password_confirm','As senhas não coincidem.')
        return data


class PatientAccountForm(forms.ModelForm):
    class Meta:
        model=PortalAccount
        fields=['phone']

    def clean_phone(self):
        phone=only_digits(self.cleaned_data['phone'])
        if len(phone)!=11:
            raise ValidationError('Informe um celular válido com DDD.')
        return phone


class PatientClinicalIntakeForm(forms.ModelForm):
    """Ficha de identificação e contato; perguntas de saúde ficam na anamnese.

    Campos antigos permanecem no banco para preservar históricos existentes, mas
    o formulario nao os solicita nem os altera durante atualizações cadastrais.
    """
    cpf = forms.CharField(label="CPF", required=False, max_length=14,
        widget=forms.TextInput(attrs={"inputmode":"numeric", "placeholder":"000.000.000-00"}))
    birth_city = forms.CharField(label="Município de nascimento", max_length=100, required=True)
    birth_state = forms.CharField(label="UF de nascimento", max_length=2, required=False)

    class Meta:
        model = PatientProfile
        fields = [
            'cpf', 'cpf_missing_reason', 'social_name', 'birth_date', 'sex',
            'mother_name', 'mother_unknown', 'nationality', 'birth_country',
            'birth_state', 'birth_city',
            'phone', 'phone_alt', 'postal_code', 'address_street', 'address_number',
            'address_complement', 'address_neighborhood', 'address_city', 'address_state',
            'guardian_name', 'guardian_phone', 'emergency_name', 'emergency_phone',
        ]
        widgets = {'birth_date':forms.DateInput(attrs={'type':'date'},format='%Y-%m-%d')}

    def clean_cpf(self):
        cpf=only_digits(self.cleaned_data['cpf'])
        if not cpf:
            return None
        if not cpf_valid(cpf):
            raise ValidationError('Informe um CPF válido.')
        if PatientProfile.objects.filter(cpf=cpf).exclude(pk=self.instance.pk).exists():
            raise ValidationError('CPF já está vinculado a outro paciente. Solicite conferência antes de continuar.')
        return cpf

    def clean_phone(self):
        value=only_digits(self.cleaned_data['phone'])
        if len(value) not in (10,11):
            raise ValidationError('Informe DDD e telefone.')
        return value

    def clean_postal_code(self):
        value=only_digits(self.cleaned_data['postal_code'])
        if len(value)!=8:
            raise ValidationError('Informe CEP com 8 digitos.')
        return value

    def clean(self):
        data=super().clean()
        if not data.get('cpf') and not data.get('cpf_missing_reason'):
            self.add_error('cpf_missing_reason','Informe a justificativa para não apresentar CPF.')
        if data.get('mother_unknown') is False and not data.get('mother_name'):
            self.add_error('mother_name','Informe o nome ou marque que é desconhecido.')
        dob=data.get('birth_date')
        if dob and (dob > date.today() or dob.year<1900):
            self.add_error('birth_date','Data inválida.')
        elif dob:
            age=date.today().year-dob.year-((date.today().month,date.today().day)<(dob.month,dob.day))
            if age<18 and not data.get('guardian_name'):
                self.add_error('guardian_name','Informe o responsável legal.')
        for field in ['birth_state','address_state']:
            value=(data.get(field) or '').upper().strip()
            if value and (len(value)!=2 or not value.isalpha()):
                self.add_error(field,'Use a sigla da UF com duas letras.')
            data[field]=value
        if (data.get('birth_country') or '').strip().casefold() in ('brasil','brazil') and not data.get('birth_state'):
            self.add_error('birth_state','Informe a UF de nascimento.')
        for field in ['phone_alt','emergency_phone','guardian_phone']:
            value=only_digits(data.get(field,''))
            if value and len(value) not in (10,11):
                self.add_error(field,'Informe telefone com DDD.')
            data[field]=value
        return data


class PatientCompleteRegistrationForm(PatientClinicalIntakeForm):
    """Ficha de cadastro similar aos campos do PEC; sem integração com e-SUS.

    Identificação e endereço são necessários para cadastro/nota fiscal.
    Os dados de saúde/autodeclaração são voluntários e não geram diagnóstico.
    """
    race_color = forms.ChoiceField(label='Raça/cor (autodeclaração opcional)',
        choices=PatientProfile.RACE, required=False, initial='nao_informada')
    data_awareness = forms.BooleanField(required=True,
        label='Li o aviso de privacidade. Entendo que os campos de saúde e autodeclaração são opcionais e usados apenas para cuidado e cadastro.')

    class Meta(PatientClinicalIntakeForm.Meta):
        fields = PatientClinicalIntakeForm.Meta.fields + [
            'cns', 'father_name', 'race_color', 'ethnicity', 'marital_status',
            'educational_level', 'occupation', 'employment', 'private_health_plan',
            'traditional_community', 'homeless', 'disabilities',
            'hypertension', 'diabetes', 'heart_disease', 'kidney_disease',
            'respiratory_disease', 'pregnancy', 'smoking', 'other_conditions',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['birth_country'].initial = 'Brasil'
        self.fields['nationality'].initial = 'brasileira'
        self.fields['cpf'].help_text = 'Obrigatório para pedir NFS-e. Se não possuir CPF, justifique; solicitação de NFS-e ficará pendente.'
        self.fields['race_color'].required = False
        for field in ('cns', 'father_name', 'ethnicity', 'marital_status',
                      'educational_level', 'occupation', 'employment',
                      'private_health_plan', 'traditional_community', 'homeless',
                      'disabilities', 'hypertension', 'diabetes', 'heart_disease',
                      'kidney_disease', 'respiratory_disease', 'pregnancy', 'smoking',
                      'other_conditions'):
            self.fields[field].required = False

    def clean_cns(self):
        cns = only_digits(self.cleaned_data.get('cns'))
        if cns and len(cns) != 15:
            raise ValidationError('O CNS deve ter 15 dígitos, quando informado.')
        return cns

    def clean(self):
        values = super().clean()
        if not values.get('race_color'):
            values['race_color'] = 'nao_informada'
        return values


SELF_REGISTRATION_SECTIONS = [
    ('Identificação e dados pessoais', ('cpf','cpf_missing_reason','social_name','birth_date','sex','race_color','cns','mother_name','mother_unknown','father_name','marital_status')),
    ('Naturalidade', ('nationality','birth_country','birth_state','birth_city','ethnicity')),
    ('Endereço e contato', ('phone','phone_alt','postal_code','address_street','address_number','address_complement','address_neighborhood','address_city','address_state')),
    ('Responsáveis e emergência', ('guardian_name','guardian_phone','emergency_name','emergency_phone')),
    ('Dados sociais opcionais', ('educational_level','occupation','employment','private_health_plan','traditional_community','homeless')),
    ('Condições de saúde autorreferidas — opcionais', ('disabilities','hypertension','diabetes','heart_disease','kidney_disease','respiratory_disease','pregnancy','smoking','other_conditions')),
    ('Privacidade', ('data_awareness',)),
]


def self_registration_groups(form):
    return [{'title':title,'fields':[form[key] for key in keys]} for title, keys in SELF_REGISTRATION_SECTIONS]


CLINICAL_SECTIONS=[
    ('Identificação do paciente', ('cpf','cpf_missing_reason','social_name','birth_date','sex','mother_name','mother_unknown')),
    ('Naturalidade', ('nationality','birth_country','birth_state','birth_city')),
    ('Contato e endereço', ('phone','phone_alt','postal_code','address_street','address_number','address_complement','address_neighborhood','address_city','address_state')),
    ('Responsável legal e emergência', ('guardian_name','guardian_phone','emergency_name','emergency_phone')),
]


def clinical_groups(form):
    return [{'title':title,'fields':[form[key] for key in fields]} for title,fields in CLINICAL_SECTIONS]


class SignInForm(forms.Form):
    email = forms.EmailField(label="E-mail")
    password = forms.CharField(label="Senha", widget=forms.PasswordInput)

class InvoiceRequestForm(forms.Form):
    appointment = forms.UUIDField(label="Consulta", required=False, widget=forms.HiddenInput)

class InvoiceResponseForm(forms.ModelForm):
    document = forms.FileField(label="PDF da nota fiscal", required=False, widget=forms.ClearableFileInput(attrs={"accept":"application/pdf"}))

    class Meta:
        model = InvoiceRequest
        fields = ["status", "invoice_number", "staff_response"]
        labels = {"status": "Situação", "invoice_number": "Número da NFS-e", "staff_response": "Mensagem ao paciente"}

    def clean_document(self):
        upload = self.cleaned_data.get("document")
        if upload:
            if upload.size > 5 * 1024 * 1024:
                raise ValidationError("O PDF deve ter no máximo 5 MB.")
            signature = upload.read(5)
            upload.seek(0)
            if signature != b"%PDF-":
                raise ValidationError("Formato inválido: envie um PDF.")
        return upload

class ExamOrderForm(forms.ModelForm):
    class Meta:
        model = ExamOrder
        fields = ["title", "instructions", "status"]
        labels = {"title": "Exame", "instructions": "Orientações", "status": "Etapa"}

class ClinicalEntryForm(forms.ModelForm):
    class Meta:
        model = ClinicalEntry
        fields = ["title", "summary", "release_to_patient"]
        labels = {"title": "Título", "summary": "Resumo clínico", "release_to_patient": "Permitir visualização pelo paciente"}


class PatientDocumentUploadForm(forms.Form):
    title = forms.CharField(label="Identificação do documento", max_length=160,
                            help_text="Por exemplo: Receita da consulta / Plano alimentar de acompanhamento")
    transcription = forms.CharField(
        label="Transcrição integral da receita (conferida com o PDF)",
        max_length=12000,
        required=False,
        widget=forms.Textarea(attrs={"rows": 10, "autocomplete": "off", "spellcheck": "false"}),
        help_text="Digite exatamente o conteúdo da receita assinada. A transcrição é para leitura, não substitui o PDF original. Não são geradas prescrições pelo sistema.")
    confirmed_transcription = forms.BooleanField(
        label="Confirmei a transcrição com o PDF original do profissional emissor",
        required=False)
    document = forms.FileField(label="Arquivo PDF original", widget=forms.ClearableFileInput(attrs={"accept":".pdf,application/pdf"}))

    def __init__(self, *args, kind=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.kind = kind
        if kind == "prescription":
            self.fields['transcription'].required = True
            self.fields['confirmed_transcription'].required = True
        else:
            self.fields.pop('transcription')
            self.fields.pop('confirmed_transcription')

    def clean_transcription(self):
        transcript = self.cleaned_data.get('transcription', '').strip()
        if self.kind == "prescription" and not transcript:
            raise ValidationError("Transcreva integralmente a receita original antes de publicar.")
        return transcript

    def clean_document(self):
        upload = self.cleaned_data["document"]
        if upload.size < 8 or upload.size > 5 * 1024 * 1024:
            raise ValidationError("O PDF deve ter até 5 MB.")
        if upload.read(5) != b"%PDF-":
            raise ValidationError("Arquivo inválido. Envie um documento PDF.")
        upload.seek(0)
        return upload


class PatientProtocolForm(forms.ModelForm):
    clinical_confirmation = forms.BooleanField(
        label='Confirmo a necessidade individual após avaliação médica, considerando contraindicações.',
        required=True)

    class Meta:
        model = PatientProtocol
        fields = ['protocol','clinical_justification','instructions','scheduled_for']
        widgets = {
            'clinical_justification':forms.Textarea(attrs={'rows':4}),
            'instructions':forms.Textarea(attrs={'rows':3}),
            'scheduled_for':forms.DateInput(attrs={'type':'date'}),
        }
        labels = {'protocol':'Protocolo selecionado','clinical_justification':'Necessidade clínica individual',
                  'instructions':'Orientações ao paciente','scheduled_for':'Data prevista (opcional)'}

    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['protocol'].queryset=Protocol.objects.filter(active=True).order_by('sort_order','name')

    def clean_clinical_justification(self):
        text = (self.cleaned_data.get('clinical_justification') or '').strip()
        if len(text) < 15:
            raise forms.ValidationError('Descreva a necessidade clínica individual (ao menos 15 caracteres).')
        return text
