from django.db import migrations, models
from django.db.models import Q


def migrate_old_bookings(apps, schema_editor):
    Appointment = apps.get_model("clinic", "Appointment")
    # Do not erase historical transactions silently if an old installation processed payments.
    if Appointment.objects.exclude(payment_id__isnull=True).exclude(payment_id="").exists() or \
       Appointment.objects.filter(paid_at__isnull=False).exists() or \
       Appointment.objects.exclude(payment_preference_id="").exists() or \
       Appointment.objects.exclude(checkout_url="").exists() or \
       Appointment.objects.filter(status="payment_review").exists():
        raise RuntimeError("A migração encontrou histórico de cobrança. Faça backup e avaliação financeira antes de eliminar campos de pagamento.")
    Appointment.objects.filter(status__in=["hold", "expired", "payment_review"]).update(status="cancelled")


class Migration(migrations.Migration):
    dependencies = [("clinic", "0001_initial")]
    operations = [
        migrations.RunPython(migrate_old_bookings, migrations.RunPython.noop),
        migrations.RemoveConstraint(model_name="appointment", name="unique_active_appointment_per_slot"),
        migrations.RemoveField(model_name="invoicerequest", name="document"),
        migrations.AddField(model_name="invoicerequest", name="document_pdf", field=models.BinaryField(blank=True, null=True, editable=False)),
        migrations.RemoveField(model_name="service", name="deposit_cents"),
        migrations.RemoveField(model_name="appointment", name="amount_cents"),
        migrations.RemoveField(model_name="appointment", name="hold_expires_at"),
        migrations.RemoveField(model_name="appointment", name="checkout_url"),
        migrations.RemoveField(model_name="appointment", name="payment_preference_id"),
        migrations.RemoveField(model_name="appointment", name="payment_id"),
        migrations.RemoveField(model_name="appointment", name="paid_at"),
        migrations.AlterField(model_name="appointment", name="status", field=models.CharField(
            max_length=20, default="confirmed", choices=[("confirmed", "Confirmada"), ("cancelled", "Cancelada")]
        )),
        migrations.AddConstraint(model_name="appointment", constraint=models.UniqueConstraint(
            fields=("slot",), condition=Q(status="confirmed"), name="unique_active_appointment_per_slot"
        )),
    ]
