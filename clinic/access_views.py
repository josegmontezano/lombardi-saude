"""Professional enrollment and management-controlled approval."""
from django import forms
from django.contrib import messages
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from .models import StaffAccessRequest
from .access_control import can_manage_clinic, is_approved_doctor

User = get_user_model()
JOBS = [(k, v) for k, v in User.STAFF_JOBS if k]

class StaffSignupForm(forms.Form):
    name = forms.CharField(label="Nome completo", min_length=4, max_length=140)
    email = forms.EmailField(label="E-mail", max_length=254)
    requested_job = forms.ChoiceField(label="Área de atuação", choices=[("", "Selecione sua função")] + JOBS)
    password = forms.CharField(label="Crie uma senha", min_length=12, max_length=128,
                                widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))
    password_confirm = forms.CharField(label="Confirme a senha", widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))
    acknowledge = forms.BooleanField(label="Entendo que meu cadastro será analisado e que não terei acesso antes da aprovação da gestão.")
    website = forms.CharField(required=False, max_length=100)

    def clean_name(self):
        name = " ".join(self.cleaned_data["name"].split())
        if len(name.split()) < 2:
            raise forms.ValidationError("Informe nome e sobrenome.")
        return name

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Este e-mail já está cadastrado ou aguardando aprovação.")
        return email

    def clean_website(self):
        if self.cleaned_data["website"].strip():
            raise forms.ValidationError("Cadastro inválido.")
        return ""

    def clean(self):
        values = super().clean()
        if values.get("password") and values.get("password_confirm"):
            if values["password"] != values["password_confirm"]:
                self.add_error("password_confirm", "As senhas são diferentes.")
            else:
                try:
                    validate_password(values["password"])
                except ValidationError as exc:
                    self.add_error("password", exc)
        return values

def signup(request):
    if request.user.is_authenticated:
        return redirect("master_access" if can_manage_clinic(request.user) else "professional_access_home")
    form = StaffSignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    username=data["email"], email=data["email"],
                    password=data["password"], first_name=data["name"],
                    role=User.STAFF, staff_job="", is_active=False,
                    is_staff=False, is_superuser=False,
                    clinical_access=False, financial_access=False,
                )
                StaffAccessRequest.objects.create(user=user, requested_job=data["requested_job"])
            messages.success(request, "Cadastro recebido e enviado para aprovação da administração.")
            return redirect("professional_signup_received")
        except IntegrityError:
            form.add_error("email", "Já existe um cadastro com este e-mail.")
    response = render(request, "clinic/professional_signup.html", {"form": form}, status=400 if request.method == "POST" else 200)
    response["Cache-Control"] = "no-store"
    return response

def signup_received(request):
    return render(request, "clinic/professional_signup_received.html")

def management_gate(request):
    if not request.user.is_authenticated:
        return redirect("professional_login")
    if not can_manage_clinic(request.user):
        raise PermissionDenied("Somente administradores ou médicos aprovados podem gerenciar cadastros.")
    if getattr(request.user, "must_change_password", False):
        return redirect("/gestao/password_change/")
    return None

def management_access(request):
    gate = management_gate(request)
    if gate:
        return gate
    response = render(request, "clinic/management_access.html", {
        "requests": StaffAccessRequest.objects.select_related("user", "reviewed_by").all()[:200],
        "pending_count": StaffAccessRequest.objects.filter(status=StaffAccessRequest.PENDING).count(),
        "jobs": JOBS,
    })
    response["Cache-Control"] = "private, no-store"
    return response

@require_POST
def management_decision(request, pk):
    gate = management_gate(request)
    if gate:
        return gate
    choice = request.POST.get("decision")
    if choice not in (StaffAccessRequest.APPROVED, StaffAccessRequest.REJECTED):
        return HttpResponseBadRequest("Decisão inválida.")
    with transaction.atomic():
        application = get_object_or_404(StaffAccessRequest.objects.select_for_update(), pk=pk)
        if application.status != StaffAccessRequest.PENDING:
            return HttpResponseBadRequest("Este cadastro já foi analisado.")
        user = User.objects.select_for_update().get(pk=application.user_id)
        if choice == StaffAccessRequest.APPROVED:
            job = request.POST.get("job", "")
            if job not in dict(JOBS):
                return HttpResponseBadRequest("Selecione uma função válida.")
            user.role = User.STAFF
            user.staff_job = job
            user.is_active = True
            user.is_staff = job == User.JOB_DOCTOR
            user.is_superuser = False
            user.clinical_access = False
            user.financial_access = False
            user.save(update_fields=["role", "staff_job", "is_active", "is_staff",
                                     "is_superuser", "clinical_access", "financial_access"])
        else:
            user.is_active = False
            user.is_staff = False
            user.is_superuser = False
            user.save(update_fields=["is_active", "is_staff", "is_superuser"])
        application.status = choice
        application.reviewed_by = request.user
        application.reviewed_at = timezone.now()
        application.save(update_fields=["status", "reviewed_by", "reviewed_at"])
    messages.success(request, "A solicitação foi analisada.")
    return redirect("management_access")

def professional_access_home(request):
    if not request.user.is_authenticated:
        return redirect("professional_login")
    if not request.user.is_active or request.user.role not in (User.STAFF, User.ADMIN):
        return redirect("professional_login")
    if can_manage_clinic(request.user):
        return redirect("master_access")
    if getattr(request.user, "must_change_password", False):
        return redirect("/gestao/password_change/")
    response = render(request, "clinic/professional_access_home.html")
    response["Cache-Control"] = "private, no-store"
    return response


def master_gate(request):
    if not request.user.is_authenticated:
        return redirect("professional_login")
    if not can_manage_clinic(request.user):
        raise PermissionDenied("Acesso exclusivo da gestão e médicos aprovados.")
    if getattr(request.user, "must_change_password", False):
        return redirect("professional_password_change")
    return None

def master_access(request):
    gate=master_gate(request)
    if gate:
        return gate
    response=render(request,"clinic/master_overview.html",{
        "pending_count":StaffAccessRequest.objects.filter(status=StaffAccessRequest.PENDING).count(),
    })
    response["Cache-Control"]="private, no-store"
    return response

def professional_password_change(request):
    if not request.user.is_authenticated or not request.user.is_active:
        return redirect("professional_login")
    form=PasswordChangeForm(request.user,request.POST or None)
    if request.method=="POST" and form.is_valid():
        user=form.save()
        if user.must_change_password:
            user.must_change_password=False
            user.save(update_fields=["must_change_password"])
        update_session_auth_hash(request,user)
        messages.success(request,"Sua senha foi alterada. O acesso administrativo está disponível.")
        return redirect("master_access" if can_manage_clinic(user) else "professional_access_home")
    response=render(request,"clinic/password_change.html",{"form":form})
    response["Cache-Control"]="private, no-store"
    return response
