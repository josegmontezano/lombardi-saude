"""Identified service evaluations, private analytics, and professional moderation."""
from datetime import date, timedelta
import re
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Avg, Count, Case, When, Value, IntegerField, Sum
from django.db.models.functions import TruncMonth
from django.http import JsonResponse, HttpResponseNotFound
from django.shortcuts import render, redirect
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from .models import ClinicReview, User
from .access_control import can_manage_clinic
from .professional_views import _can_publish

SCORES = ("reception", "nursing_technician", "nursing", "doctor")
LABELS = [("reception", "Recepção"), ("nursing_technician", "Técnico de Enfermagem"),
          ("nursing", "Enfermagem"), ("doctor", "Médico")]
PERIODS = 12

class ReviewForm(forms.Form):
    patient_name = forms.CharField(label="Nome completo", max_length=140, min_length=3, required=True)
    patient_email = forms.EmailField(label="E-mail", required=True)
    patient_phone = forms.CharField(label="Telefone com DDD", max_length=20, required=True)
    unit = forms.ChoiceField(choices=[("", "Selecione a unidade")] + ClinicReview.UNITS)
    reception = forms.TypedChoiceField(coerce=int, choices=[(i, str(i)) for i in range(6)])
    nursing_technician = forms.TypedChoiceField(coerce=int, choices=[(i, str(i)) for i in range(6)])
    nursing = forms.TypedChoiceField(coerce=int, choices=[(i, str(i)) for i in range(6)])
    doctor = forms.TypedChoiceField(coerce=int, choices=[(i, str(i)) for i in range(6)])
    private_comment = forms.CharField(max_length=750, required=False, widget=forms.Textarea)
    website = forms.CharField(required=False, max_length=100)

    def clean_patient_name(self):
        name=" ".join(self.cleaned_data["patient_name"].split())
        if len(name.split()) < 2:
            raise forms.ValidationError("Informe seu nome e sobrenome.")
        return name

    def clean_patient_phone(self):
        digits=re.sub(r"\D","",self.cleaned_data["patient_phone"])
        if len(digits) not in (10,11):
            raise forms.ValidationError("Informe telefone com DDD (10 ou 11 dígitos).")
        return digits

    def clean_website(self):
        v = self.cleaned_data.get("website", "")
        if v.strip():
            raise forms.ValidationError("Solicitação inválida.")
        return ""

def _summary(qs):
    # Adapted NPS. For each 0-5 sector evaluation: promoters=5,
    # passives=4, detractors=0-3. Pooled sector assessments yield clinic NPS.
    values = qs.aggregate(
        count=Count("id"),
        **{"avg_" + k: Avg(k) for k in SCORES},
        **{k + "_promoters": Sum(Case(When(**{k: 5}, then=Value(1)), default=Value(0), output_field=IntegerField())) for k in SCORES},
        **{k + "_detractors": Sum(Case(When(**{k + "__lte": 3}, then=Value(1)), default=Value(0), output_field=IntegerField())) for k in SCORES},
    )
    count = values["count"] or 0
    sectors = []
    for key, label in LABELS:
        promoters = values[key + "_promoters"] or 0
        detractors = values[key + "_detractors"] or 0
        sectors.append({
            "key": key, "label": label,
            "average": round(values["avg_" + key], 2) if count else None,
            "nps": round(100 * (promoters - detractors) / count, 1) if count else None,
            "promoters": promoters, "detractors": detractors,
        })
    return {
        "count": count,
        "nps": round(sum(x["nps"] for x in sectors)/len(sectors), 1) if count else None,
        "sectors": sectors,
        "promoters": sum(x["promoters"] for x in sectors),
        "detractors": sum(x["detractors"] for x in sectors),
        "evaluations": count * len(SCORES),
    }

def _range():
    now = timezone.localdate()
    return [(now.year + (now.month - 1 - i)//12, (now.month - 1 - i)%12 + 1) for i in reversed(range(PERIODS))]

def _series(qs):
    y, m = _range()[0]
    cutoff = date(y, m, 1)
    annotations = {
        "count": Count("id"),
        **{"avg_" + k: Avg(k) for k in SCORES},
        **{k + "_promoters": Sum(Case(When(**{k: 5}, then=Value(1)), default=Value(0), output_field=IntegerField())) for k in SCORES},
        **{k + "_detractors": Sum(Case(When(**{k + "__lte": 3}, then=Value(1)), default=Value(0), output_field=IntegerField())) for k in SCORES},
    }
    groups = qs.filter(created_at__date__gte=cutoff).annotate(
        month=TruncMonth("created_at")
    ).values("month").annotate(**annotations).order_by("month")
    keyed = {(g["month"].year, g["month"].month): g for g in groups}
    output = []
    for year, month in _range():
        row = keyed.get((year, month))
        c = row["count"] if row else 0
        val = {"month": f"{month:02d}/{str(year)[2:]}", "count": c}
        for key in SCORES:
            val[key] = round(row["avg_" + key], 2) if c else None
            val[key + "_nps"] = round(100 * ((row[key + "_promoters"] or 0) - (row[key + "_detractors"] or 0))/c, 1) if c else None
        val["nps"] = round(sum(val[k + "_nps"] for k in SCORES)/4, 1) if c else None
        output.append(val)
    return output

def _manager(request):
    u = request.user
    if not u.is_authenticated:
        return redirect("professional_login")
    if not can_manage_clinic(u):
        raise PermissionDenied("Painel disponível somente à gestão.")
    if getattr(u, "must_change_password", False):
        return redirect("/gestao/password_change/")
    return None

def _review_context(form=None):
    # Show only reviews explicitly approved by the professional. Never expose
    # name, email, phone or private comments in public rendered templates.
    return {
        "form": form or ReviewForm(),
        "approved_reviews": ClinicReview.objects.filter(status=ClinicReview.APPROVED).order_by("-reviewed_at")[:12],
        "scores": list(range(6)),
        "fields": LABELS,
    }

@require_GET
def review_page(request):
    return render(request, "clinic/reviews.html", _review_context())

@require_POST
def review_submit(request):
    form = ReviewForm(request.POST)
    if not form.is_valid():
        return render(request, "clinic/reviews.html", _review_context(form), status=400)
    last = request.session.get("lx_last_review")
    if last:
        try:
            if timezone.now().timestamp() - float(last) < 120:
                form.add_error(None, "Aguarde alguns minutos antes de enviar outra avaliação.")
                return render(request, "clinic/reviews.html", _review_context(form), status=429)
        except (ValueError,TypeError):
            pass
    cleaned = form.cleaned_data
    if ClinicReview.objects.filter(patient_email__iexact=cleaned["patient_email"], created_at__gte=timezone.now()-timedelta(hours=24)).count() >= 3:
        form.add_error(None, "Limite diário de avaliações atingido para este e-mail.")
        return render(request, "clinic/reviews.html", _review_context(form), status=429)
    ClinicReview.objects.create(
        patient_name=cleaned["patient_name"], patient_email=cleaned["patient_email"].strip().lower(),
        patient_phone=cleaned["patient_phone"], unit=cleaned["unit"],
        reception=cleaned["reception"], nursing_technician=cleaned["nursing_technician"],
        nursing=cleaned["nursing"], doctor=cleaned["doctor"],
        private_comment=cleaned["private_comment"].strip(),
        status=ClinicReview.PENDING,
    )
    request.session["lx_last_review"] = timezone.now().timestamp()
    messages.success(request, "Avaliação recebida! A publicação depende da análise do profissional responsável.")
    return redirect("review_page")

@require_GET
def review_public_data(request):
    # Old public JSON endpoint is retired. Dashboard data is private.
    response = HttpResponseNotFound("Indicadores disponíveis somente no painel privado.")
    response["Cache-Control"] = "no-store"
    return response

def _reviewer_gate(request):
    if not request.user.is_authenticated:
        return redirect("professional_login")
    if not _can_publish(request.user):
        raise PermissionDenied("Somente profissionais autorizados podem analisar avaliações.")
    if getattr(request.user,"must_change_password",False):
        return redirect("/gestao/password_change/")
    return None

@require_GET
def review_moderation(request):
    gate = _reviewer_gate(request)
    if gate:
        return gate
    unit = request.GET.get("unit","geral")
    if unit not in ("geral",ClinicReview.CAMPO_GRANDE,ClinicReview.ALEGRE):
        unit = "geral"
    qs = ClinicReview.objects.select_related("reviewed_by")
    if unit != "geral":
        qs=qs.filter(unit=unit)
    status=request.GET.get("status","pending")
    if status not in ("pending","approved","rejected","all"):
        status="pending"
    if status!="all":
        qs=qs.filter(status=status)
    response=render(request,"clinic/review_moderation.html",{
        "reviews":qs.order_by("-created_at")[:200],
        "unit":unit,"filter_status":status,
        "pending_count":ClinicReview.objects.filter(status=ClinicReview.PENDING).count(),
        "statuses":ClinicReview.STATUSES,
    })
    response["Cache-Control"]="private, no-store"
    return response

@require_POST
def review_decision(request,pk):
    gate=_reviewer_gate(request)
    if gate:
        return gate
    from django.shortcuts import get_object_or_404
    from django.db import transaction
    action=request.POST.get("decision")
    if action not in (ClinicReview.APPROVED,ClinicReview.REJECTED):
        from django.http import HttpResponseBadRequest
        return HttpResponseBadRequest("Decisão inválida.")
    with transaction.atomic():
        review=get_object_or_404(ClinicReview.objects.select_for_update(),pk=pk)
        review.status=action
        review.reviewed_by=request.user
        review.reviewed_at=timezone.now()
        review.save(update_fields=["status","reviewed_by","reviewed_at"])
    messages.success(request,"Avaliação analisada. Status atualizado.")
    return redirect("review_moderation")

@require_GET
def review_dashboard(request):
    denied = _manager(request)
    if denied:
        return denied
    unit = request.GET.get("unit", "geral")
    if unit not in ("geral", ClinicReview.CAMPO_GRANDE, ClinicReview.ALEGRE):
        unit = "geral"
    qs = ClinicReview.objects.all()
    if unit != "geral":
        qs = qs.filter(unit=unit)
    stats = _summary(qs)
    series = _series(qs)
    recent = qs.order_by("-created_at")[:50]
    pending = qs.filter(status=ClinicReview.PENDING).count()
    if request.GET.get("format") == "json":
        response = JsonResponse({"stats": stats, "series": series})
        response["Cache-Control"] = "private, no-store"
        return response
    return render(request, "clinic/review_dashboard.html", {
        "unit": unit, "stats": stats, "series": series,
        "recent": recent, "unit_names": dict(ClinicReview.UNITS),
        "pending_count": pending
    })
