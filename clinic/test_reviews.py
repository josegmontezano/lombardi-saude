from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse
from .models import ClinicReview
from .review_views import _summary, _series

User=get_user_model()

def valid_review(**kwargs):
    return {
        "patient_name":"Paciente Exemplo", "patient_email":"teste@example.com",
        "patient_phone":"(21) 99999-8888", "unit":"alegre",
        "reception":5,"nursing_technician":4,"nursing":3,"doctor":5,
        "private_comment":"Sugestão privada",
        **kwargs,
    }

class ReviewTests(TestCase):
    def test_blank_public_form_and_no_public_dashboard(self):
        r=self.client.get(reverse("review_page"))
        self.assertEqual(r.status_code,200)
        self.assertContains(r,"Avalie o seu atendimento")
        self.assertContains(r,'name="patient_name"')
        self.assertContains(r,'name="patient_email"')
        self.assertContains(r,'name="patient_phone"')
        self.assertContains(r,'name="doctor"')
        self.assertNotContains(r,"O que nossos pacientes avaliam")
        self.assertNotContains(r,"Sugestão privada")
        self.assertEqual(self.client.get(reverse("review_public_data")).status_code,404)
        self.assertIsNone(_summary(ClinicReview.objects.all())["nps"])

    def test_new_review_pending_and_nps_private(self):
        response=self.client.post(reverse("review_submit"),valid_review())
        self.assertEqual(response.status_code,302)
        obj=ClinicReview.objects.get()
        self.assertEqual(obj.status,ClinicReview.PENDING)
        self.assertEqual(obj.patient_name,"Paciente Exemplo")
        self.assertEqual(obj.patient_phone,"21999998888")
        self.assertEqual(_summary(ClinicReview.objects.all())["nps"],25.0)
        self.assertEqual(_series(ClinicReview.objects.all())[-1]["count"],1)
        public=self.client.get(reverse("review_page"))
        self.assertNotContains(public,"Paciente Exemplo")
        self.assertNotContains(public,"Sugestão privada")
        self.assertNotContains(public,"Experiências compartilhadas")

    def test_validation_of_all_required_fields_and_invalid_scores(self):
        bad=valid_review(reception=6)
        r=self.client.post(reverse("review_submit"),bad)
        self.assertEqual(r.status_code,400)
        self.assertEqual(ClinicReview.objects.count(),0)
        for field in ("patient_name","patient_email","patient_phone","unit","reception","nursing_technician","nursing","doctor"):
            bad=valid_review()
            bad.pop(field)
            self.assertEqual(self.client.post(reverse("review_submit"),bad).status_code,400, field)
        self.assertEqual(self.client.post(reverse("review_submit"),valid_review(private_comment="")).status_code,302)

    def test_dashboard_and_moderation_permissions(self):
        self.assertEqual(self.client.get(reverse("review_dashboard")).status_code,302)
        self.assertEqual(self.client.get(reverse("review_moderation")).status_code,302)
        patient=User.objects.create_user(username="sample",email="sample@example.test",password="secret-pass-123",role=User.PATIENT)
        self.client.force_login(patient)
        self.assertEqual(self.client.get(reverse("review_dashboard")).status_code,403)
        self.assertEqual(self.client.get(reverse("review_moderation")).status_code,403)
        self.client.logout()
        admin=User.objects.create_superuser(username="adminx",email="adminx@example.test",password="secret-pass-123")
        self.client.force_login(admin)
        for unit in ("geral","alegre","campo_grande"):
            self.assertEqual(self.client.get(reverse("review_dashboard")+f"?unit={unit}").status_code,200)
            self.assertEqual(self.client.get(reverse("review_dashboard")+f"?unit={unit}&format=json").status_code,200)
            self.assertEqual(self.client.get(reverse("review_moderation")+f"?unit={unit}").status_code,200)

    def test_professional_approval_and_rejection(self):
        item=ClinicReview.objects.create(unit="alegre",patient_name="Maria Teste",patient_email="maria@example.test",patient_phone="28999999999",reception=1,nursing_technician=2,nursing=3,doctor=4,private_comment="Não exibir este comentário.")
        doctor=User.objects.create_user(username="doctorx",email="doctorx@example.test",password="secret-pass-123",role=User.STAFF,staff_job=User.JOB_DOCTOR,is_staff=True)
        self.client.force_login(doctor)
        self.assertEqual(self.client.get(reverse("review_moderation")).status_code,200)
        self.assertEqual(self.client.get(reverse("review_dashboard")).status_code,200)
        self.assertEqual(self.client.post(reverse("review_decision",args=[item.pk]),{"decision":"invalid"}).status_code,400)
        self.assertEqual(self.client.post(reverse("review_decision",args=[item.pk]),{"decision":"approved"}).status_code,302)
        item.refresh_from_db()
        self.assertEqual(item.status,ClinicReview.APPROVED)
        self.assertEqual(item.reviewed_by_id,doctor.pk)
        response=self.client.get(reverse("review_page"))
        self.assertContains(response,"Experiências compartilhadas")
        self.assertContains(response,"Alegre/ES")
        self.assertNotContains(response,"Maria Teste")
        self.assertNotContains(response,"maria@example.test")
        self.assertNotContains(response,"Não exibir este comentário.")
        self.assertEqual(self.client.post(reverse("review_decision",args=[item.pk]),{"decision":"rejected"}).status_code,302)
        self.assertNotContains(self.client.get(reverse("review_page")),"Experiências compartilhadas")

    def test_home_navigation_and_merged_pages(self):
        r=self.client.get(reverse("home"))
        self.assertEqual(r.status_code,200)
        self.assertNotContains(r,"Conhecimento, experiência")
        self.assertNotContains(r,"lx-specialties-grid")
        self.assertNotContains(r,"Avaliar atendimento")
        self.assertNotContains(r,"lx-ux-section")
        self.assertContains(r,"Tirando Dúvidas com a")
        self.assertContains(r,"Especialidades e Serviços")
        about=self.client.get(reverse("about"))
        self.assertContains(about,"Conhecimento, experiência")
        special=self.client.get(reverse("specialties"))
        self.assertContains(special,"lx-specialties-grid")
        self.assertContains(special,"Saúde pós-bariátrica")
        self.assertEqual(self.client.get(reverse("services")).status_code,301)
        self.assertEqual(self.client.get(reverse("community")).status_code,302)
        vlog=self.client.get(reverse("vlog_index"))
        self.assertContains(vlog,"Enviar dúvida ou mensagem")
        self.assertContains(vlog,'id="enviar-duvida"')
        self.assertNotContains(vlog,"Vlog da")

    def test_unified_question_form_post(self):
        data={"kind":"question","name":"Pessoa", "email":"pessoa@example.com","text":"Como funciona a avaliação de saúde preventiva?", "privacy_ack":"on"}
        response=self.client.post(reverse("community_submit"),data)
        self.assertIn(response.status_code,[302,400])
        if response.status_code==302:
            self.assertEqual(response.url,"/vlog/#enviar-duvida")

    def test_privacy_section_stays_hidden(self):
        self.assertNotContains(self.client.get(reverse("contact")),"SEGURANÇA E PRIVACIDADE")
        self.assertNotContains(self.client.get(reverse("home")),">Privacidade</a>")
