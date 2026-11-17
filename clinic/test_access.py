from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from .models import StaffAccessRequest

User=get_user_model()

def application(email="novo@example.test", **override):
    return {
        "name":"Novo Profissional",
        "email":email,
        "requested_job":"reception",
        "password":"SenhaForte#A2026",
        "password_confirm":"SenhaForte#A2026",
        "acknowledge":"on",
        **override,
    }

class AccessOnboardingTests(TestCase):
    def test_signup_ui_and_validation(self):
        response=self.client.get(reverse("professional_login"))
        self.assertContains(response,"Solicitar cadastro profissional")
        response=self.client.get(reverse("professional_signup"))
        self.assertEqual(response.status_code,200)
        self.assertContains(response,"aprovação do administrador da clínica")
        self.assertContains(response,'name="password_confirm"')
        invalid=self.client.post(reverse("professional_signup"),application(name="Fulano",password="123",password_confirm="123"))
        self.assertEqual(invalid.status_code,400)
        self.assertFalse(User.objects.filter(email="novo@example.test").exists())

    def test_no_master_route_and_patient_gets_login_not_403(self):
        self.assertEqual(self.client.get("/profissional/mestre/").status_code, 302)
        self.assertEqual(self.client.get("/profissional/mestre/1/decidir/").status_code, 404)
        patient=User.objects.create_user(username="patient-logged",email="patient-logged@example.test",
                                           password="testpassword123",role=User.PATIENT)
        self.client.force_login(patient)
        self.assertRedirects(self.client.get(reverse("professional_access_home")),reverse("professional_login"),fetch_redirect_response=False)
        self.assertEqual(self.client.get(reverse("professional_login")).status_code,200)
        self.assertNotContains(self.client.get(reverse("professional_login")),"Acesso mestre")

    def test_management_role_not_superuser_can_approve(self):
        self.client.post(reverse("professional_signup"),application(email="another@example.test"))
        request=StaffAccessRequest.objects.get()
        admin=User.objects.create_user(username="manager",email="manager@example.test",
                                        password="testpassword123",role=User.ADMIN,is_staff=False,is_superuser=False)
        self.client.force_login(admin)
        self.assertEqual(self.client.get(reverse("management_access")).status_code,200)
        self.assertEqual(self.client.post(reverse("management_decision",args=[request.pk]),{"decision":"approved","job":"reception"}).status_code,302)
        self.assertTrue(User.objects.get(email="another@example.test").is_active)

    def test_registration_creates_inactive_account(self):
        response=self.client.post(reverse("professional_signup"),application())
        self.assertEqual(response.status_code,302)
        account=User.objects.get(email="novo@example.test")
        self.assertFalse(account.is_active)
        self.assertFalse(account.is_staff)
        self.assertFalse(account.is_superuser)
        self.assertFalse(account.clinical_access)
        self.assertFalse(account.financial_access)
        self.assertTrue(account.check_password("SenhaForte#A2026"))
        self.assertEqual(account.staff_access_request.status,"pending")
        self.assertEqual(self.client.post(reverse("professional_login"),{"username":"novo@example.test","password":"SenhaForte#A2026"}).status_code,200)
        self.assertEqual(self.client.post(reverse("professional_signup"),application()).status_code,400)

    def test_only_master_can_approve_registration(self):
        self.client.post(reverse("professional_signup"),application())
        application_obj=StaffAccessRequest.objects.get()
        target=reverse("management_decision",args=[application_obj.pk])
        self.assertEqual(self.client.get(reverse("management_access")).status_code,302)
        self.assertEqual(self.client.post(target,{"decision":"approved","job":"reception"}).status_code,302)
        self.assertEqual(application_obj.status,StaffAccessRequest.PENDING)
        normal=User.objects.create_user(username="normal",email="normal@example.test",password="testpassword123",role=User.STAFF)
        self.client.force_login(normal)
        self.assertEqual(self.client.get(reverse("management_access")).status_code,403)
        self.assertEqual(self.client.post(target,{"decision":"approved","job":"doctor"}).status_code,403)
        self.client.logout()
        boss=User.objects.create_superuser(username="master123",email="boss@example.test",password="testpassword123")
        self.client.force_login(boss)
        self.assertEqual(self.client.get(reverse("management_access")).status_code,200)
        self.assertEqual(self.client.post(target,{"decision":"approved","job":"invalid"}).status_code,400)
        self.assertEqual(self.client.post(target,{"decision":"approved","job":"reception"}).status_code,302)
        account=User.objects.get(email="novo@example.test")
        self.assertTrue(account.is_active)
        self.assertFalse(account.is_staff)
        self.assertFalse(account.is_superuser)
        self.assertFalse(account.clinical_access)
        self.assertEqual(account.staff_job,"reception")
        application_obj.refresh_from_db()
        self.assertEqual(application_obj.status,"approved")
        self.assertEqual(application_obj.reviewed_by,boss)
        self.assertEqual(self.client.post(target,{"decision":"rejected"}).status_code,400)
        self.client.logout()
        login=self.client.post(reverse("professional_login"),{"username":"novo@example.test","password":"SenhaForte#A2026"})
        self.assertRedirects(login,reverse("professional_access_home"),fetch_redirect_response=False)

    def test_rejected_account_is_not_active(self):
        self.client.post(reverse("professional_signup"),application(email="rejected@example.test"))
        master=User.objects.create_superuser(username="master234",email="boss2@example.test",password="testpassword123")
        self.client.force_login(master)
        request=StaffAccessRequest.objects.get()
        self.assertEqual(self.client.post(reverse("management_decision",args=[request.pk]),{"decision":"rejected"}).status_code,302)
        self.assertFalse(User.objects.get(email="rejected@example.test").is_active)
        self.assertEqual(StaffAccessRequest.objects.get().status,"rejected")
