"""Agenda transacional de horários livres e notificações, sem pagamento."""
from datetime import timedelta
from django.db import IntegrityError, transaction
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone
from django.urls import reverse
from .models import Appointment, AuditEvent, Notification, Slot, User


class BookingUnavailable(Exception):
    """Horário solicitado já está indisponível ou é inválido."""


def notify(user, title, text, category, link=""):
    return Notification.objects.create(recipient=user, title=title, message=text, category=category, link=link)


def notify_team(title, text, category, link="", finance=False):
    if finance:
        q = Q(is_superuser=True) | Q(role=User.ADMIN) | Q(role=User.STAFF, financial_access=True, staff_job="") | Q(role=User.STAFF, staff_job=User.JOB_FINANCE) | Q(role=User.STAFF, staff_job=User.JOB_RECEPTION)
    else:
        q = Q(is_superuser=True) | Q(role__in=[User.STAFF, User.ADMIN])
    staff = User.objects.filter(is_active=True).filter(q).distinct()
    return Notification.objects.bulk_create([
        Notification(recipient=u, title=title, message=text, category=category,
                     link=(reverse("reception_overview") if u.staff_job == User.JOB_RECEPTION and finance else link))
        for u in staff
    ])


def notify_patient_request(patient, title, text, category, link, finance=False):
    """Centraliza avisos ao setor responsável quando um paciente inicia uma ação.

    Não inclui conteúdo clínico sensível nas notificações; detalhes ficam nas telas
    autenticadas, com escopo e permissões apropriados.
    """
    if patient.role != User.PATIENT:
        raise ValueError("Solicitações precisam partir de um paciente.")
    return notify_team(title, text, category, link, finance=finance)


def audit(actor, action, subject, reference=""):
    AuditEvent.objects.create(actor=actor, action=action, subject=subject, reference_id=str(reference))


def free_slots():
    """Exibe somente horários sem agendamentos confirmados."""
    blockers = Appointment.objects.filter(slot_id=OuterRef("pk"), status=Appointment.CONFIRMED)
    return (Slot.objects.filter(active=True, service__active=True, starts_at__gt=timezone.now() + timedelta(hours=3))
            .annotate(blocked=Exists(blockers)).filter(blocked=False)
            .select_related("service", "professional").order_by("starts_at"))


def reserve(patient, slot_id):
    """Confirma imediatamente o horário. Trava a linha do Slot para evitar dupla marcação."""
    try:
        with transaction.atomic():
            slot = (Slot.objects.select_for_update().select_related("service")
                    .get(pk=slot_id, active=True, service__active=True,
                         starts_at__gt=timezone.now() + timedelta(hours=3)))
            if Appointment.objects.filter(slot=slot, status=Appointment.CONFIRMED).exists():
                raise BookingUnavailable("Este horário já foi reservado. Escolha outro.")
            appointment = Appointment.objects.create(patient=patient, slot=slot, status=Appointment.CONFIRMED)
            notify(patient, "Consulta confirmada",
                   "Seu agendamento foi confirmado. Confira a data e o horário no Portal do Paciente.",
                   "booking_confirmed", "/paciente/consultas/")
            notify_patient_request(patient, "Nova consulta agendada",
                                   "Um paciente confirmou um horário de consulta no portal. Confira a agenda.",
                                   "staff_booking", "/funcionario/")
            audit(patient, "booking_confirmed", "appointment", appointment.pk)
            return appointment
    except (Slot.DoesNotExist, IntegrityError) as exc:
        raise BookingUnavailable("Horário indisponível. Escolha outro.") from exc
