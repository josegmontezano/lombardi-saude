from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from .access_control import can_manage_clinic, is_approved_doctor
from .doctor_admin_permissions import MEDICAL_MANAGER_GROUP
from .models import StaffAccessRequest, ClinicReview, VlogVideo

User=get_user_model()


class MedicalAdministratorTests(TestCase):
    def setUp(self):
        self.doctor=User.objects.create_user(
            username="doctor-authorized",
            email="doctor-authorized@example.test",
            password="A-very-strong-password-026!",
            role=User.STAFF,
            staff_job=User.JOB_DOCTOR,
            is_active=True,
            is_staff=True,
        )
        self.reception=User.objects.create_user(
            username="reception-not-admin",
            email="reception-not-admin@example.test",
            password="A-very-strong-password-026!",
            role=User.STAFF,
            staff_job=User.JOB_RECEPTION,
            is_active=True,
            is_staff=False,
        )
        self.master=User.objects.create_superuser(
            username="master-2",email="master-2@example.test",
            password="A-very-strong-password-026!"
        )

    def test_doctor_has_master_panel_and_management_actions(self):
        self.assertTrue(can_manage_clinic(self.doctor))
        self.assertTrue(is_approved_doctor(self.doctor))
        self.client.force_login(self.doctor)
        names=("master_access","management_access","professional_posts",
               "professional_post_new","professional_analytics",
               "professional_submissions","professional_instagram",
               "review_moderation","review_dashboard")
        for name in names:
            response=self.client.get(reverse(name))
            self.assertEqual(response.status_code,200,name)
            self.assertContains(response, "Menu lateral administrativo")
            self.assertContains(response,'class="lx-admin-shell"')
        self.assertContains(self.client.get(reverse("master_access")),"Acesso mestre")
        self.assertContains(self.client.get(reverse("master_access")),"Cadastros")
        self.assertRedirects(
            self.client.get(reverse("professional_access_home")),
            reverse("master_access"), fetch_redirect_response=False
        )

    def test_professional_onboarding_and_approval(self):
        candidate=User.objects.create_user(
            username="doctor-pending", email="doctor-pending@example.test",
            password="A-very-strong-password-026!",
            role=User.STAFF,staff_job="",is_active=False,is_staff=False,
        )
        requested=StaffAccessRequest.objects.create(user=candidate,requested_job=User.JOB_DOCTOR)
        self.assertFalse(can_manage_clinic(candidate))
        self.client.force_login(self.reception)
        self.assertEqual(self.client.get(reverse("master_access")).status_code,403)
        self.assertEqual(self.client.post(
            reverse("management_decision", args=[requested.pk]),
            {"decision":"approved","job":User.JOB_DOCTOR}
        ).status_code,403)
        self.client.logout()
        self.client.force_login(self.doctor)
        result=self.client.post(
            reverse("management_decision", args=[requested.pk]),
            {"decision":"approved","job":User.JOB_DOCTOR}
        )
        self.assertEqual(result.status_code,302)
        candidate.refresh_from_db()
        self.assertTrue(can_manage_clinic(candidate))
        self.assertTrue(candidate.is_staff)
        self.assertFalse(candidate.is_superuser)
        self.client.force_login(candidate)
        self.assertEqual(self.client.get(reverse("master_access")).status_code,200)

    def test_advanced_django_admin_uses_scoped_role_permissions(self):
        self.assertTrue(self.doctor.groups.filter(name=MEDICAL_MANAGER_GROUP).exists())
        self.assertTrue(self.doctor.has_perm("clinic.add_vlogvideo"))
        self.assertTrue(self.doctor.has_perm("clinic.change_vlogvideo"))
        self.assertTrue(self.doctor.has_perm("clinic.view_clinicreview"))
        self.assertFalse(self.doctor.has_perm("clinic.change_clinicreview"))
        self.assertFalse(self.doctor.has_perm("clinic.change_user"))
        self.assertFalse(self.reception.has_perm("clinic.view_clinicreview"))
        self.client.force_login(self.doctor)
        self.assertEqual(self.client.get("/gestao/").status_code,200)
        self.assertEqual(self.client.get("/gestao/clinic/vlogvideo/").status_code,200)
        self.assertEqual(self.client.get("/gestao/clinic/clinicreview/").status_code,200)

    def test_inactive_or_downgraded_doctor_is_blocked(self):
        self.doctor.staff_job=User.JOB_NURSE
        self.doctor.save(update_fields=["staff_job"])
        self.doctor.refresh_from_db()
        self.assertFalse(can_manage_clinic(self.doctor))
        self.assertFalse(self.doctor.groups.filter(name=MEDICAL_MANAGER_GROUP).exists())
        self.client.force_login(self.doctor)
        self.assertEqual(self.client.get(reverse("master_access")).status_code,403)
        self.assertEqual(self.client.get(reverse("review_dashboard")).status_code,403)
        self.assertFalse(self.doctor.has_perm("clinic.change_vlogvideo"))
        self.doctor.staff_job=User.JOB_DOCTOR
        self.doctor.is_active=False
        self.doctor.save(update_fields=["staff_job","is_active"])
        self.assertFalse(can_manage_clinic(self.doctor))
        self.assertFalse(self.doctor.groups.filter(name=MEDICAL_MANAGER_GROUP).exists())
