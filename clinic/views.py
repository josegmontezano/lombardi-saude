from django.conf import settings
"""Patient/staff portals with direct appointment confirmation, without payment."""
import uuid
from functools import wraps
from urllib.parse import urlencode
import hashlib
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, get_user_model, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.forms import PasswordChangeForm
from django.db.models import Prefetch
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.http import HttpResponse, HttpResponseBadRequest, Http404, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from django.utils import timezone
from django.views.decorators.http import require_POST, require_GET

from .forms import PatientRegisterForm, SignInForm, InvoiceRequestForm, InvoiceResponseForm, ExamOrderForm, ClinicalEntryForm, PatientProtocolForm, PatientAccountForm, PatientClinicalIntakeForm, PatientCompleteRegistrationForm, PatientDocumentUploadForm, clinical_groups, self_registration_groups
from .models import Appointment, AuditEvent, ClinicalEntry, ExamOrder, InvoiceRequest, Notification, Slot, PatientProfile, PortalAccount, Protocol, LoginAttempt, PatientDocument, PatientProtocol, fiscal_data_for_patient
from .services import reserve, free_slots, notify, notify_patient_request, audit, BookingUnavailable

User = get_user_model()

DEMO_PATIENT_USERNAME = "demo-paciente-lombardi"

def is_demo_patient(user):
    return getattr(user, "username", "") == DEMO_PATIENT_USERNAME and user.role == User.PATIENT


def staff_required(fn):
    @wraps(fn)
    @login_required(login_url="staff_login")
    def wrapper(request, *args, **kwargs):
        if request.user.role not in (User.STAFF, User.ADMIN) and not request.user.is_superuser:
            raise PermissionDenied
        return fn(request, *args, **kwargs)
    return wrapper



def is_doctor(user):
    return bool(user.is_authenticated and user.role == User.STAFF and user.staff_job == User.JOB_DOCTOR)


def can_write_clinical(user):
    # Older staff entries without a job retain previously granted clinical access.
    return bool(is_doctor(user) or (user.role in (User.ADMIN, User.STAFF) and not user.staff_job and user.clinical_access))


def can_finance(user):
    return bool(user.is_superuser or (user.role == User.ADMIN and user.financial_access) or
                (user.role == User.STAFF and (user.staff_job == User.JOB_FINANCE or
                                               (not user.staff_job and user.financial_access))))


def can_view_protocol_queue(user):
    return bool(user.is_superuser or user.role == User.ADMIN or
                (user.role == User.STAFF and user.staff_job in (User.JOB_DOCTOR, User.JOB_NURSE,
                                                                 User.JOB_TECH, User.JOB_RECEPTION)) or
                (user.role == User.STAFF and not user.staff_job and user.clinical_access))


def can_reception_monitor(user):
    return bool(user.is_superuser or user.role == User.ADMIN or
                (user.role == User.STAFF and user.staff_job == User.JOB_RECEPTION))


def doctor_required(fn):
    @wraps(fn)
    @staff_required
    def wrapper(request, *args, **kwargs):
        if not is_doctor(request.user):
            raise PermissionDenied
        return fn(request, *args, **kwargs)
    return wrapper


def protocol_queue_required(fn):
    @wraps(fn)
    @staff_required
    def wrapper(request, *args, **kwargs):
        if not can_view_protocol_queue(request.user):
            raise PermissionDenied
        return fn(request, *args, **kwargs)
    return wrapper


def reception_required(fn):
    @wraps(fn)
    @staff_required
    def wrapper(request, *args, **kwargs):
        if not can_reception_monitor(request.user):
            raise PermissionDenied
        return fn(request, *args, **kwargs)
    return wrapper

def finance_required(fn):
    @wraps(fn)
    @staff_required
    def wrapper(request, *args, **kwargs):
        if not can_finance(request.user):
            raise PermissionDenied
        return fn(request, *args, **kwargs)
    return wrapper


def clinical_required(fn):
    @wraps(fn)
    @staff_required
    def wrapper(request, *args, **kwargs):
        if not can_write_clinical(request.user):
            raise PermissionDenied
        return fn(request, *args, **kwargs)
    return wrapper


def patient_required(fn):
    @wraps(fn)
    @login_required(login_url="patient_login")
    def wrapper(request, *args, **kwargs):
        if request.user.role != User.PATIENT:
            raise PermissionDenied
        if not is_demo_patient(request.user) and PortalAccount.objects.filter(user=request.user).exists():
            if not PatientProfile.objects.filter(user=request.user, registration_completed_at__isnull=False).exists():
                messages.info(request, 'Complete sua ficha cadastral para utilizar o Portal do Paciente.')
                return redirect('patient_complete_registration')
        return fn(request, *args, **kwargs)
    return wrapper


def home(request):
    return render(request, "clinic/home.html")


def specialties(request):
    return render(request, "clinic/specialties.html")


def technology(request):
    return render(request, "clinic/technology.html")

def about(request):
    return render(request, "clinic/about.html")


def services(request):
    return render(request, "clinic/services.html")


def content(request):
    return render(request, "clinic/content.html")


def contact(request):
    return render(request, "clinic/contact.html")


def privacy(request):
    return render(request, "clinic/privacy.html")


def _login_key(email):
    return hashlib.sha256(email.lower().strip().encode('utf-8')).hexdigest()


def _login_limited(email):
    attempt = LoginAttempt.objects.filter(identifier=_login_key(email)).first()
    return bool(attempt and attempt.locked_until and attempt.locked_until > timezone.now())


def _record_bad_login(email):
    now = timezone.now()
    with transaction.atomic():
        attempt, _ = LoginAttempt.objects.select_for_update().get_or_create(identifier=_login_key(email))
        if now - attempt.window_started_at > timedelta(minutes=15):
            attempt.attempts = 0
            attempt.window_started_at = now
        attempt.attempts += 1
        if attempt.attempts >= 5:
            attempt.locked_until = now + timedelta(minutes=15)
        attempt.save(update_fields=['attempts','window_started_at','locked_until'])


@login_required(login_url='staff_login')
def master_change_password(request):
    if request.user.role not in (User.ADMIN, User.STAFF):
        raise PermissionDenied
    form = PasswordChangeForm(request.user, request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        User.objects.filter(pk=request.user.pk).update(must_change_password=False)
        request.user.must_change_password = False
        update_session_auth_hash(request, request.user)
        audit(request.user,'password_rotated','user',request.user.pk)
        messages.success(request,'Sua senha foi atualizada com segurança.')
        return redirect('staff_home')
    return render(request, 'clinic/password_change.html',{'form':form})


def _login(request, portal):
    if request.user.is_authenticated:
        return redirect("patient_home" if request.user.role == User.PATIENT else "staff_home")
    form = SignInForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        email, password = form.cleaned_data["email"].strip().lower(), form.cleaned_data["password"]
        if _login_limited(email):
            messages.error(request, "Muitas tentativas de acesso. Tente novamente após 15 minutos.")
        else:
            candidate = User.objects.filter(email__iexact=email, is_active=True).first()
            user = authenticate(request, username=candidate.username, password=password) if candidate else None
            if user and ((portal == "patient" and user.role == User.PATIENT) or (portal == "staff" and (user.role in [User.STAFF, User.ADMIN] or user.is_superuser))):
                LoginAttempt.objects.filter(identifier=_login_key(email)).delete()
                login(request, user)
                if user.must_change_password:
                    return redirect('master_change_password')
                return redirect("patient_home" if portal == "patient" else "staff_home")
            _record_bad_login(email)
            messages.error(request, "E-mail ou senha inválidos.")
    return render(request, "clinic/login.html", {"form": form, "portal": portal})


def patient_login(request):
    return _login(request, "patient")


def staff_login(request):
    return _login(request, "staff")


def patient_register(request):
    if request.user.is_authenticated:
        return redirect('patient_home' if request.user.role==User.PATIENT else 'staff_home')
    form=PatientRegisterForm(request.POST or None)
    if request.method=='POST' and form.is_valid():
        try:
            validate_password(form.cleaned_data['password'])
            with transaction.atomic():
                name=form.cleaned_data['name'].strip()
                user=User.objects.create_user(
                    username='p-'+uuid.uuid4().hex,
                    email=form.cleaned_data['email'],
                    password=form.cleaned_data['password'],
                    first_name=name[:150],
                    role=User.PATIENT, patient_verified=False,
                    is_staff=False,is_superuser=False,clinical_access=False,financial_access=False)
                PortalAccount.objects.create(user=user,phone=form.cleaned_data['phone'],privacy_acknowledged_at=timezone.now())
                audit(user,'portal_account_created','user',user.pk)
                notify_patient_request(user, 'Novo cadastro de paciente',
                    'Uma pessoa criou conta no Portal do Paciente. Verifique a fila de cadastros.',
                    'patient_registration', reverse('staff_patient_search'))
            login(request,user)
            messages.success(request,'Conta criada. Complete seu cadastro para acessar o portal e solicitar nota fiscal.')
            return redirect('patient_complete_registration')
        except (ValidationError,IntegrityError) as exc:
            if isinstance(exc,ValidationError):
                for item in exc.messages: form.add_error('password',item)
            else: form.add_error('email','Já existe uma conta com esse e-mail.')
    return render(request,'clinic/register.html',{'form':form})




@login_required(login_url='patient_login')
def patient_complete_registration(request):
    if request.user.role != User.PATIENT:
        raise PermissionDenied
    if is_demo_patient(request.user):
        return redirect('patient_home')
    profile = PatientProfile.objects.filter(user=request.user).first()
    initial = {}
    if not profile:
        account = PortalAccount.objects.filter(user=request.user).first()
        if account:
            initial['phone'] = account.phone
    form = PatientCompleteRegistrationForm(request.POST or None, instance=profile, initial=initial)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            record = form.save(commit=False)
            record.user = request.user
            record.registration_completed_at = timezone.now()
            record.privacy_acknowledged_at = timezone.now()
            record.save()
            audit(request.user, 'patient_registration_completed', 'patient_profile', record.pk)
            notify_patient_request(request.user, 'Cadastro completo para conferência',
                'Um paciente concluiu o preenchimento cadastral. Confira a identificação.',
                'patient_profile_completed', reverse('staff_patient_search'))
        messages.success(request, 'Cadastro completo salvo. Seus documentos clínicos continuam sujeitos à validação de identidade.')
        return redirect('patient_home')
    return render(request, 'clinic/patient_complete_registration.html', {
        'form':form, 'groups':self_registration_groups(form),
        'is_update': bool(profile and profile.registration_completed_at),
    })


@require_POST
def logout_view(request):
    logout(request)
    return redirect("home")


@patient_required
def patient_home(request):
    return render(request, "clinic/patient_home.html", {
        "confirmed": request.user.appointments.filter(status=Appointment.CONFIRMED).count(),
        "invoice_count": request.user.invoice_requests.count(),
        "exams_count": request.user.exams.count() if request.user.patient_verified else None,
        "demo_account": is_demo_patient(request.user),
        "protocol_count": request.user.patient_protocols.count() if request.user.patient_verified else 0,
    })


@patient_required
def patient_profile(request):
    account=PortalAccount.objects.filter(user=request.user).first()
    if not account:
        messages.warning(request,'Entre em contato com a recepção para atualizar os dados de sua conta.')
        return redirect('patient_home')
    form=PatientAccountForm(request.POST or None,instance=account)
    if request.method=='POST' and form.is_valid():
        with transaction.atomic():
            form.save()
            audit(request.user,'portal_phone_updated','portal_account',request.user.pk)
            notify_patient_request(request.user, 'Paciente atualizou contato',
                'Um paciente alterou seus dados de contato. Confira o cadastro interno.',
                'patient_contact_update', reverse('staff_patient_search'))
        messages.success(request,'Celular atualizado.')
        return redirect('patient_profile')
    return render(request,'clinic/profile.html',{'form':form,'account':account})


@staff_required
def protocol_catalog(request):
    protocols = Protocol.objects.filter(active=True).order_by('sort_order','name')
    return render(request, 'clinic/protocols.html', {'protocols': protocols})


@patient_required
def book(request):
    if request.method == "POST" and is_demo_patient(request.user):
        messages.warning(request, "Conta de demonstração: não é permitido confirmar consultas reais.")
        return redirect("book")
    if request.method == "POST":
        try:
            slot_id = int(request.POST.get("slot_id", "0"))
            reserve(request.user, slot_id)
            messages.success(request, "Consulta confirmada! Você pode conferir os detalhes em Minhas consultas.")
            return redirect("my_bookings")
        except (ValueError, BookingUnavailable) as exc:
            messages.error(request, str(exc) if isinstance(exc, BookingUnavailable) else "Selecione um horário válido.")
            return redirect("book")
    return render(request, "clinic/book.html", {"slots": free_slots()[:120]})


@patient_required
def my_bookings(request):
    bookings = request.user.appointments.select_related("slot__service").order_by("-created_at")[:70]
    return render(request, "clinic/bookings.html", {"bookings": bookings})


@patient_required
def my_exams(request):
    exams = request.user.exams.order_by("-created_at")[:80] if request.user.patient_verified else []
    return render(request, "clinic/exams.html", {"exams": exams})


@patient_required
def my_records(request):
    records = request.user.records.filter(release_to_patient=True).order_by("-created_at")[:80] if request.user.patient_verified else []
    return render(request, "clinic/records.html", {"records": records})




DOCUMENT_TITLES = {
    PatientDocument.PRESCRIPTION: "Minhas Receitas",
    PatientDocument.DIET: "Minhas Dietas",
}


def _document_kind(kind):
    if kind not in DOCUMENT_TITLES:
        raise Http404("Categoria não encontrada")
    return kind


@patient_required
def my_documents(request, kind):
    kind = _document_kind(kind)
    can_view = request.user.patient_verified and not is_demo_patient(request.user)
    documents = PatientDocument.objects.filter(patient=request.user, kind=kind, active=True)[:80] if can_view else []
    response = render(request, "clinic/patient_documents.html", {
        "documents": documents, "kind": kind, "page_title": DOCUMENT_TITLES[kind], "can_view": can_view,
        "demo_account": is_demo_patient(request.user),
    })
    response["Cache-Control"] = "private, no-store"
    return response


@patient_required
def download_document(request, document_id):
    if not request.user.patient_verified or is_demo_patient(request.user):
        raise PermissionDenied
    doc = get_object_or_404(PatientDocument, pk=document_id, patient=request.user, active=True)
    audit(request.user, "patient_document_download", "patient_document", doc.pk)
    response = HttpResponse(bytes(doc.document_pdf), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="Lombardi_{doc.kind}_{doc.pk}.pdf"'
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    response["Content-Security-Policy"] = "default-src 'none'; sandbox"
    return response


@patient_required
def print_original_prescription(request, document_id):
    # A impressão sempre usa os bytes do PDF original enviado pela equipe.
    if not request.user.patient_verified or is_demo_patient(request.user):
        raise PermissionDenied
    doc = get_object_or_404(PatientDocument, pk=document_id, patient=request.user,
                            kind=PatientDocument.PRESCRIPTION, active=True)
    audit(request.user, "patient_prescription_original_print", "patient_document", doc.pk)
    response = HttpResponse(bytes(doc.document_pdf), content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="Receita_Original_Lombardi_{doc.pk}.pdf"'
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    response["Content-Security-Policy"] = "default-src 'none'; sandbox"
    return response


@clinical_required
def staff_patient_documents(request, user_id, kind):
    kind = _document_kind(kind)
    patient = get_object_or_404(User, pk=user_id, role=User.PATIENT)
    if is_demo_patient(patient):
        raise PermissionDenied("Conta de demonstração não admite documentos clínicos.")
    if not patient.patient_verified:
        messages.warning(request, "A identidade do paciente precisa ser conferida antes de disponibilizar PDFs clínicos.")
        return redirect(reverse('staff_patient_search')+'?'+urlencode({'email': patient.email}))
    form = PatientDocumentUploadForm(request.POST or None, request.FILES or None, kind=kind)
    if request.method == 'POST' and form.is_valid():
        upload = form.cleaned_data['document']
        with transaction.atomic():
            doc = PatientDocument(patient=patient, kind=kind,
                                  title=form.cleaned_data['title'], document_pdf=upload.read(),
                                  transcription=form.cleaned_data.get('transcription', ''),
                                  uploaded_by=request.user)
            doc.full_clean()
            doc.save()
            notify(patient, "Nova receita disponível" if kind == PatientDocument.PRESCRIPTION else "Nova dieta disponível",
                   "Sua receita transcrita e o PDF original estão disponíveis." if kind == PatientDocument.PRESCRIPTION else "Um PDF foi incluído no seu portal. Acesse para baixar o documento.",
                   "prescription_ready" if kind == PatientDocument.PRESCRIPTION else "diet_ready",
                   reverse("my_documents", kwargs={"kind": kind}))
            audit(request.user, "patient_document_uploaded", kind, doc.pk)
        messages.success(request, "PDF disponibilizado ao paciente; notificação enviada.")
        return redirect(reverse("staff_patient_documents", kwargs={"user_id": patient.pk, "kind": kind}))
    documents = PatientDocument.objects.filter(patient=patient, kind=kind, active=True).select_related("uploaded_by")[:80]
    return render(request, "clinic/staff_patient_documents.html", {
        "patient": patient, "kind": kind, "page_title": DOCUMENT_TITLES[kind], "form": form, "documents": documents,
    })


@clinical_required
def staff_download_document(request, document_id):
    doc = get_object_or_404(PatientDocument, pk=document_id, active=True)
    audit(request.user, "staff_document_download", doc.kind, doc.pk)
    response = HttpResponse(bytes(doc.document_pdf), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="Lombardi_{doc.kind}_{doc.pk}.pdf"'
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    response["Content-Security-Policy"] = "default-src 'none'; sandbox"
    return response


@require_POST
@clinical_required
def staff_archive_document(request, document_id):
    doc = get_object_or_404(PatientDocument, pk=document_id, active=True)
    with transaction.atomic():
        doc.active = False
        doc.save(update_fields=["active"])
        audit(request.user, "patient_document_archived", doc.kind, doc.pk)
        notify(doc.patient, "Documento atualizado", "Um arquivo anteriormente publicado foi retirado para revisão pela equipe.",
               "patient_document_archived", reverse("my_documents", kwargs={"kind": doc.kind}))
    messages.success(request, "Documento retirado da visualização do paciente. Registro preservado para auditoria.")
    return redirect(reverse("staff_patient_documents", kwargs={"user_id": doc.patient_id, "kind": doc.kind}))

@patient_required
def my_invoices(request):
    return render(request, "clinic/invoices.html", {"invoices": request.user.invoice_requests.order_by("-created_at")[:70]})


@require_POST
@patient_required
def request_invoice(request):
    if is_demo_patient(request.user):
        messages.warning(request, "Conta de demonstração: solicitações fiscais reais estão desabilitadas.")
        return redirect("my_invoices")
    appointment_id = request.POST.get("appointment_id", "").strip()
    appointment = None
    if appointment_id:
        try:
            appointment = Appointment.objects.get(pk=uuid.UUID(appointment_id), patient=request.user)
        except (ValueError, Appointment.DoesNotExist):
            return HttpResponseBadRequest("Consulta inválida.")
    duplicate = InvoiceRequest.objects.filter(patient=request.user, appointment=appointment, status__in=[InvoiceRequest.REQUESTED, InvoiceRequest.REVIEWING, InvoiceRequest.NEED_DATA]).exists()
    if duplicate:
        messages.info(request, "Já existe uma solicitação em andamento.")
        return redirect("my_invoices")
    profile = PatientProfile.objects.filter(user=request.user).first()
    if not profile or not profile.cpf or not profile.registration_completed_at:
        messages.warning(request, 'Informe CPF válido e complete o cadastro para solicitar a nota fiscal.')
        return redirect('patient_complete_registration')
    with transaction.atomic():
        invoice = InvoiceRequest.objects.create(patient=request.user, appointment=appointment,
            billing_snapshot=fiscal_data_for_patient(request.user, profile))
        notify_patient_request(request.user, "Nova solicitação de nota fiscal", "Um paciente solicitou nota fiscal. Confira a fila financeira e responda no portal.", "invoice_requested", reverse('staff_invoices'), finance=True)
        notify(request.user, "Solicitação recebida", "Sua solicitação de nota fiscal foi encaminhada ao setor financeiro.", "invoice_requested", "/paciente/notas/")
        audit(request.user, "invoice_requested", "invoice", invoice.pk)
    messages.success(request, "Solicitação enviada ao setor financeiro.")
    return redirect("my_invoices")


@patient_required
def download_invoice(request, invoice_id):
    invoice = get_object_or_404(InvoiceRequest, pk=invoice_id, patient=request.user, status=InvoiceRequest.DONE)
    if not invoice.document_pdf:
        raise PermissionDenied
    audit(request.user, "invoice_download", "invoice", invoice.pk)
    response = HttpResponse(bytes(invoice.document_pdf), content_type="application/pdf")
    safe_number = "".join(c for c in (invoice.invoice_number or str(invoice.pk)) if c.isalnum() or c in "-_")
    response["Content-Disposition"] = f'attachment; filename="NFSe_Lombardi_{safe_number}.pdf"' 
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@staff_required
def staff_home(request):
    return render(request, "clinic/staff_home.html", {
        "can_doctor": is_doctor(request.user) or can_write_clinical(request.user),
        "can_finance": can_finance(request.user),
        "can_protocol_queue": can_view_protocol_queue(request.user),
        "can_reception": can_reception_monitor(request.user),
        "job_label": request.user.get_staff_job_display() if request.user.staff_job else "Equipe",
        "confirmed_bookings": Appointment.objects.filter(status=Appointment.CONFIRMED).count(),
        "recent_bookings": Appointment.objects.select_related("patient", "slot__service").order_by("-created_at")[:20],
        "financial_access": can_finance(request.user),
    })


@finance_required
def staff_invoices(request):
    invoices = InvoiceRequest.objects.select_related("patient", "appointment").order_by("-created_at")[:150]
    return render(request, "clinic/staff_invoices.html", {"invoices": invoices})


@finance_required
def staff_invoice_billing_details(request, invoice_id):
    invoice = get_object_or_404(InvoiceRequest.objects.select_related('patient'), pk=invoice_id)
    audit(request.user, 'invoice_billing_details_viewed', 'invoice', invoice.pk)
    return render(request, 'clinic/staff_invoice_billing_details.html', {
        'invoice':invoice, 'billing':invoice.billing_data})


@finance_required
def respond_invoice(request, invoice_id):
    invoice = get_object_or_404(InvoiceRequest, pk=invoice_id)
    form = InvoiceResponseForm(request.POST or None, request.FILES or None, instance=invoice)
    if request.method == "POST" and form.is_valid():
        new_status = form.cleaned_data["status"]
        upload = form.cleaned_data.get("document")
        if new_status == InvoiceRequest.DONE and not (upload or invoice.document_pdf):
            form.add_error("document", "Anexe o PDF oficial antes de finalizar.")
        elif new_status == InvoiceRequest.DONE and not form.cleaned_data.get("invoice_number"):
            form.add_error("invoice_number", "Informe o número fiscal.")
        else:
            with transaction.atomic():
                record = form.save(commit=False)
                if upload:
                    record.document_pdf = upload.read()
                record.full_clean()
                record.save()
                notify(invoice.patient,
                       "Nota fiscal disponível" if new_status == InvoiceRequest.DONE else "Atualização da nota fiscal",
                       "O PDF da NFS-e está disponível no portal." if new_status == InvoiceRequest.DONE else (record.staff_response or "Sua solicitação foi atualizada."),
                       "invoice_ready" if new_status == InvoiceRequest.DONE else "invoice_update", "/paciente/notas/")
                audit(request.user, "invoice_response", "invoice", invoice.pk)
            messages.success(request, "Resposta registrada e notificação enviada.")
            return redirect("staff_invoices")
    return render(request, "clinic/invoice_response.html", {"invoice": invoice, "form": form})


@staff_required
def staff_patient_search(request):
    if not (can_write_clinical(request.user) or can_reception_monitor(request.user)):
        raise PermissionDenied
    email = request.GET.get("email", "").strip().lower()
    patient = None
    if email and len(email) <= 254 and "@" in email:
        patient = User.objects.filter(email__iexact=email, role=User.PATIENT).first()
    return render(request, "clinic/staff_patients.html", {"email": email, "patient": patient})


@staff_required
def staff_patient_clinical(request,user_id):
    # Clínica: não expor dados sensíveis para recepção/financeiro sem autorização clínica.
    if not can_write_clinical(request.user):
        raise PermissionDenied
    patient=get_object_or_404(User,pk=user_id,role=User.PATIENT)
    profile=PatientProfile.objects.filter(user=patient).first()
    account=PortalAccount.objects.filter(user=patient).first()
    form=PatientClinicalIntakeForm(request.POST or None,instance=profile,initial={'phone':account.phone} if not profile and account else None)
    if request.method=='POST' and form.is_valid():
        with transaction.atomic():
            item=form.save(commit=False)
            item.user=patient
            item.staff_updated_by=request.user
            item.save()
            audit(request.user,'clinical_intake_saved','patient_profile',patient.pk)
        messages.success(request,'Ficha clínica interna salva. A validação de identidade é uma etapa separada.')
        return redirect(reverse('staff_patient_search')+'?'+urlencode({'email':patient.email}))
    return render(request,'clinic/clinical_intake.html',{'patient':patient,'form':form,'groups':clinical_groups(form)})


@require_POST
@staff_required
def verify_patient(request, user_id):
    if not (request.user.is_superuser or request.user.role == User.ADMIN):
        raise PermissionDenied
    if request.POST.get("identity_confirmed") != "yes":
        return HttpResponseBadRequest("É necessária a conferência presencial da identidade.")
    patient = get_object_or_404(User, pk=user_id, role=User.PATIENT)
    if is_demo_patient(patient):
        raise PermissionDenied("Cadastro de demonstração não pode ser validado como paciente real.")
    if not PatientProfile.objects.filter(user=patient).exists():
        messages.error(request,'Preencha primeiro a ficha clínica interna. A verificação de identidade exige conferência dos dados.')
        return redirect(reverse('staff_patient_search')+'?'+urlencode({'email':patient.email}))
    patient.patient_verified = True
    patient.save(update_fields=["patient_verified"])
    PatientProfile.objects.filter(user=patient).update(verified_at=timezone.now())
    notify(patient, "Identidade validada", "O acesso aos seus exames e registros liberados foi habilitado.", "verified", "/paciente/")
    audit(request.user, "patient_verified", "patient", patient.pk)
    messages.success(request, "Identidade validada para este cadastro.")
    return redirect(reverse("staff_patient_search") + "?" + urlencode({"email": patient.email}))


def _clinical_write(request, user_id, form_class, model_name):
    patient = get_object_or_404(User, pk=user_id, role=User.PATIENT, patient_verified=True)
    form = form_class(request.POST or None)
    if request.method == "POST" and form.is_valid():
        row = form.save(commit=False)
        row.patient = patient
        row.author = request.user
        row.save()
        notify(patient, "Exame solicitado" if model_name == "exam" else "Novo registro disponível",
               "A equipe registrou uma solicitação de exame." if model_name == "exam" else "Há um registro clínico liberado para sua consulta.",
               model_name, "/paciente/exames/" if model_name == "exam" else "/paciente/prontuario/") if model_name == "exam" or row.release_to_patient else None
        audit(request.user, model_name + "_created", model_name, row.pk)
        messages.success(request, "Registro realizado.")
        return redirect(reverse("staff_patient_search") + "?" + urlencode({"email": patient.email}))
    return render(request, "clinic/clinical_form.html", {"form": form, "patient": patient, "kind": model_name})


@clinical_required
def create_exam(request, user_id):
    return _clinical_write(request, user_id, ExamOrderForm, "exam")


@clinical_required
def create_record(request, user_id):
    return _clinical_write(request, user_id, ClinicalEntryForm, "record")


@staff_required
def dashboard(request):
    now = timezone.localtime()
    period = {"slot__starts_at__year": now.year, "slot__starts_at__month": now.month}
    monthly = Appointment.objects.filter(**period)
    totals = monthly.aggregate(
        confirmed=Count("pk", filter=Q(status=Appointment.CONFIRMED)),
        cancelled=Count("pk", filter=Q(status=Appointment.CANCELLED)),
    )
    return render(request, "clinic/dashboard.html", {"totals": totals, "period": now.strftime("%m/%Y")})


def _notification_home(user):
    return reverse('patient_home' if user.role == User.PATIENT else 'staff_home')


def _safe_notification_target(target, request, fallback=None):
    """Only internal relative paths can be used for notification navigation."""
    fallback = fallback or _notification_home(request.user)
    if not target or not target.startswith('/') or target.startswith('//'):
        return fallback
    if not url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return fallback
    return target


def _reopen_notification_bell(target):
    parsed = urlsplit(target)
    query = [(key, value) for key, value in parse_qsl(parsed.query) if key != 'notificacoes']
    query.append(('notificacoes', '1'))
    return urlunsplit(('', '', parsed.path, urlencode(query), ''))


@login_required
def notifications(request):
    """Old notification URL is retained only as a redirect to the header bell."""
    return redirect(_reopen_notification_bell(_notification_home(request.user)))


@require_GET
@login_required
def notifications_more(request):
    """Page through every notice inside the bell, never exposing other users' notices."""
    try:
        offset = int(request.GET.get('offset', 0))
    except (TypeError, ValueError):
        return HttpResponseBadRequest('Paginação inválida.')
    if offset < 0 or offset > 100000:
        return HttpResponseBadRequest('Paginação inválida.')
    batch_size = 20
    rows = list(Notification.objects.filter(recipient=request.user).order_by('-created_at')[offset:offset + batch_size + 1])
    payload = [{
        'id': str(n.pk), 'title': n.title, 'message': n.message,
        'when': timezone.localtime(n.created_at).strftime('%d/%m/%Y %H:%M'),
        'unread': n.read_at is None, 'has_link': bool(n.link)
    } for n in rows[:batch_size]]
    return JsonResponse({'items': payload, 'has_more': len(rows) > batch_size, 'next_offset': offset + len(payload)})


@require_POST
@login_required
def mark_notification_read(request, notification_id):
    notice = get_object_or_404(Notification, pk=notification_id, recipient=request.user)
    if notice.read_at is None:
        Notification.objects.filter(pk=notice.pk, recipient=request.user).update(read_at=timezone.now())
    dest = _safe_notification_target(request.POST.get('return_to'), request)
    return redirect(_reopen_notification_bell(dest))


@require_POST
@login_required
def mark_all_notifications_read(request):
    Notification.objects.filter(recipient=request.user, read_at__isnull=True).update(read_at=timezone.now())
    dest = _safe_notification_target(request.POST.get('return_to'), request)
    return redirect(_reopen_notification_bell(dest))


@require_POST
@login_required
def open_notification(request, notification_id):
    notice = get_object_or_404(Notification, pk=notification_id, recipient=request.user)
    if notice.read_at is None:
        Notification.objects.filter(pk=notice.pk, recipient=request.user).update(read_at=timezone.now())
    return redirect(_safe_notification_target(notice.link, request))


@require_GET
def healthcheck(request):
    return HttpResponse("ok", content_type="text/plain")


@patient_required
def my_protocols(request):
    can_view = request.user.patient_verified and not is_demo_patient(request.user)
    qs = PatientProtocol.objects.filter(patient=request.user).select_related('protocol','prescribed_by') if can_view else PatientProtocol.objects.none()
    response = render(request, 'clinic/my_protocols.html', {'orders': qs[:100], 'can_view': can_view})
    response['Cache-Control'] = 'private, no-store'
    return response


@doctor_required
def staff_add_patient_protocol(request, user_id):
    patient = get_object_or_404(User, pk=user_id, role=User.PATIENT, patient_verified=True)
    if is_demo_patient(patient):
        raise PermissionDenied('Conta de demonstração não permite indicações reais.')
    form = PatientProtocolForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            item = form.save(commit=False)
            item.patient = patient
            item.prescribed_by = request.user
            item.full_clean()
            item.save()
            notify(patient, 'Novo protocolo individualizado',
                   'Um protocolo foi incluído pelo seu médico. Consulte Meus Protocolos.',
                   'protocol_assigned', reverse('my_protocols'))
            audit(request.user, 'patient_protocol_prescribed', 'patient_protocol', item.pk)
        messages.success(request, 'Protocolo individualizado registrado e paciente notificado.')
        return redirect('staff_protocol_queue')
    return render(request, 'clinic/staff_add_protocol.html', {'patient':patient,'form':form})


@protocol_queue_required
def staff_protocol_queue(request):
    orders = PatientProtocol.objects.filter(status=PatientProtocol.PENDING).select_related('patient','protocol','prescribed_by').order_by('scheduled_for','created_at')[:160]
    return render(request, 'clinic/staff_protocol_queue.html', {
        'orders':orders,
        'can_doctor':is_doctor(request.user),
        'read_only':not is_doctor(request.user),
    })


@require_POST
@doctor_required
def staff_protocol_update(request, protocol_id):
    item = get_object_or_404(PatientProtocol, pk=protocol_id)
    new_status = request.POST.get('status')
    if new_status not in (PatientProtocol.PERFORMED, PatientProtocol.CANCELLED):
        return HttpResponseBadRequest('Situação inválida.')
    if item.status != PatientProtocol.PENDING:
        return HttpResponseBadRequest('Somente protocolos pendentes podem ser concluídos.')
    with transaction.atomic():
        item.status = new_status
        item.save(update_fields=['status','updated_at'])
        notify(item.patient,'Atualização do protocolo',
               'O andamento de um protocolo individualizado foi atualizado.',
               'protocol_status', reverse('my_protocols'))
        audit(request.user,'patient_protocol_status_changed','patient_protocol',item.pk)
    return redirect('staff_protocol_queue')


@reception_required
def reception_overview(request):
    # Only operational fields are shown. No clinical justification, PDF, invoice
    # number, patient identity document or transcribed prescription is exposed.
    pending_protocols = PatientProtocol.objects.filter(status=PatientProtocol.PENDING).select_related('patient','protocol','prescribed_by').order_by('scheduled_for','created_at')[:80]
    pending_exams = ExamOrder.objects.exclude(status__in=['reviewed','performed']).select_related('patient','author').order_by('created_at')[:80]
    pending_invoices = InvoiceRequest.objects.exclude(status=InvoiceRequest.DONE).select_related('patient').order_by('created_at')[:80]
    recent_bookings = Appointment.objects.filter(status=Appointment.CONFIRMED).select_related('patient','slot__service').order_by('-created_at')[:60]
    # The reception monitors demand flow without gaining access to original PDFs.
    recent_prescriptions = PatientDocument.objects.filter(kind=PatientDocument.PRESCRIPTION,active=True).select_related('patient').order_by('-created_at')[:30]
    recent_diets = PatientDocument.objects.filter(kind=PatientDocument.DIET,active=True).select_related('patient').order_by('-created_at')[:30]
    response = render(request,'clinic/reception_overview.html',{
        'pending_protocols':pending_protocols,'pending_exams':pending_exams,
        'pending_invoices':pending_invoices,'recent_bookings':recent_bookings,
        'recent_prescriptions':recent_prescriptions,'recent_diets':recent_diets,
        'pending_count':PatientProtocol.objects.filter(status=PatientProtocol.PENDING).count(),
        'invoice_pending_count':InvoiceRequest.objects.exclude(status=InvoiceRequest.DONE).count(),
        'exam_pending_count':ExamOrder.objects.exclude(status__in=['reviewed','performed']).count(),
    })
    response['Cache-Control']='private, no-store'
    audit(request.user,'reception_monitor_viewed','workflow_dashboard')
    return response


# Public Vlog — no patient or professional portal is exposed.
def vlog_index(request):
    from .models import VlogVideo
    from django.utils import timezone
    videos = VlogVideo.objects.filter(published=True, publish_at__lte=timezone.now())
    categories = VlogVideo.CATEGORIES
    selected = request.GET.get('categoria', '')
    if selected and selected in dict(categories):
        videos = videos.filter(category=selected)
    else:
        selected = ''
    return render(request, 'clinic/vlog.html', {
        'videos': videos, 'categories': categories, 'selected_category': selected,
        'form': __import__('clinic.community_forms',fromlist=['PublicMessageForm']).PublicMessageForm(),
        'submissions': __import__('clinic.models',fromlist=['VisitorSubmission']).VisitorSubmission.objects.filter(status='published', publish_authorized=True).order_by('-created_at')[:50],
    })


def vlog_detail(request, slug):
    from .models import VlogVideo
    from django.utils import timezone
    video = get_object_or_404(VlogVideo, slug=slug, published=True, publish_at__lte=timezone.now())
    import base64, hashlib, hmac, json, time
    playback_token = ''
    if video.private_media_path:
        payload = base64.urlsafe_b64encode(json.dumps({'path':video.private_media_path,'post':video.pk,'ts':int(time.time())},separators=(',',':')).encode()).decode().rstrip('=')
        sig = hmac.new(settings.SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
        playback_token = payload + '.' + sig
    response = render(request, 'clinic/vlog_detail.html', {'video': video, 'private_playback_token': playback_token})
    response['Cache-Control'] = 'no-store' if video.private_media_path else 'public, max-age=120'
    return response
