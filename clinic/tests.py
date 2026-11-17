"""Execute: docker compose exec app python manage.py test clinic"""
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from .models import Appointment, InvoiceRequest, Notification, Service, Slot
from .services import reserve, free_slots, BookingUnavailable

User = get_user_model()



def seed_legacy_fiscal_fixture(patient):
    """Create a completed identity record for historical invoice tests."""
    from .models import PatientProfile
    return PatientProfile.objects.create(
        user=patient, cpf='52998224725', birth_date='1990-01-01', sex='F',
        race_color='nao_informada', mother_name='Ana', nationality='brasileira',
        birth_city='Rio de Janeiro', birth_state='RJ', birth_country='Brasil',
        phone='21999999999', postal_code='23052101', address_street='Rua Exemplo',
        address_number='10', address_neighborhood='Centro',
        address_city='Rio de Janeiro', address_state='RJ',
        registration_completed_at=timezone.now())


class BookingTests(TestCase):
    def setUp(self):
        self.doctor = User.objects.create_user("doctor", "doctor@example.com", "VeryLongPassword!-doctor", role=User.STAFF)
        self.patient = User.objects.create_user("patient", "patient@example.com", "VeryLongPassword!-patient", role=User.PATIENT)
        self.other = User.objects.create_user("other", "other@example.com", "VeryLongPassword!-other", role=User.PATIENT)
        self.service = Service.objects.create(title="Consulta teste", duration_minutes=45)
        self.slot = Slot.objects.create(service=self.service, professional=self.doctor, starts_at=timezone.now() + timedelta(days=2))

    def test_only_free_slots_visible_and_second_reservation_is_blocked(self):
        self.assertTrue(free_slots().filter(pk=self.slot.pk).exists())
        first = reserve(self.patient, self.slot.pk)
        self.assertFalse(free_slots().filter(pk=self.slot.pk).exists())
        with self.assertRaises(BookingUnavailable):
            reserve(self.other, self.slot.pk)
        self.assertEqual(first.status, Appointment.CONFIRMED)
        self.assertTrue(Notification.objects.filter(recipient=self.patient, category="booking_confirmed").exists())
        self.assertTrue(Notification.objects.filter(recipient=self.doctor, category="staff_booking").exists())

    def test_booking_view_confirms_without_external_checkout(self):
        self.client.force_login(self.patient)
        res = self.client.post(reverse("book"), {"slot_id": self.slot.pk})
        self.assertRedirects(res, reverse("my_bookings"))
        self.assertEqual(Appointment.objects.get(slot=self.slot).status, Appointment.CONFIRMED)
        self.assertContains(self.client.get(reverse("my_bookings")), "Confirmada")

    def test_cancelled_slot_is_available_again(self):
        a = reserve(self.patient, self.slot.pk)
        a.status = Appointment.CANCELLED
        a.save(update_fields=["status"])
        self.assertTrue(free_slots().filter(pk=self.slot.pk).exists())
        self.assertEqual(reserve(self.other, self.slot.pk).status, Appointment.CONFIRMED)


class InvoiceAndPrivacyTests(TestCase):
    def setUp(self):
        self.patient = User.objects.create_user("maria", "maria@example.com", "VeryLongPassword!-maria", role=User.PATIENT)
        self.other = User.objects.create_user("luiza", "luiza@example.com", "VeryLongPassword!-luiza", role=User.PATIENT)
        self.finance = User.objects.create_user("finance", "finance@example.com", "VeryLongPassword!-finance", role=User.STAFF, financial_access=True)

    def test_request_notifies_finance_and_returns_patient_acknowledgement(self):
        seed_legacy_fiscal_fixture(self.patient)
        self.client.force_login(self.patient)
        response = self.client.post(reverse("request_invoice"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(InvoiceRequest.objects.filter(patient=self.patient).count(), 1)
        self.assertTrue(Notification.objects.filter(recipient=self.finance, category="invoice_requested").exists())
        self.assertTrue(Notification.objects.filter(recipient=self.patient, category="invoice_requested").exists())

    def test_unauthorized_patient_cannot_download_others_invoice(self):
        invoice = InvoiceRequest.objects.create(patient=self.patient)
        self.client.force_login(self.other)
        response = self.client.get(reverse("download_invoice", kwargs={"invoice_id": invoice.pk}))
        self.assertEqual(response.status_code, 404)

    def test_finance_login_permissions(self):
        self.client.force_login(self.patient)
        self.assertEqual(self.client.get(reverse("staff_invoices")).status_code, 403)
        self.client.force_login(self.finance)
        self.assertEqual(self.client.get(reverse("staff_invoices")).status_code, 200)

    def test_patient_has_no_unverified_medical_data(self):
        self.client.force_login(self.patient)
        self.assertContains(self.client.get(reverse("my_records")), "conferência da identidade")


class AccountTests(TestCase):
    def test_superuser_is_admin_role(self):
        admin = User.objects.create_superuser("administrator", "admin@example.com", "VeryLongPassword!-admin")
        self.assertEqual(admin.role, User.ADMIN)
        self.assertTrue(admin.is_superuser)


class PatientIntakeTests(TestCase):
    def portal_data(self):
        return {
            'name':'Maria de Teste',
            'phone':'(21) 99999-9999',
            'email':'pessoa@example.com',
            'password':'UniquePatientPassword!123',
            'password_confirm':'UniquePatientPassword!123',
            'privacy_acknowledgement':'on',
        }

    def clinical_data(self):
        return {
            'cpf':'529.982.247-25','cns':'','social_name':'',
            'birth_date':'1990-03-10','sex':'F','race_color':'parda',
            'mother_name':'Ana de Teste','mother_unknown':'','father_name':'',
            'nationality':'brasileira','birth_country':'Brasil','birth_city':'Rio de Janeiro',
            'birth_state':'RJ','phone':'21999999999','phone_alt':'',
            'postal_code':'23000000','address_street':'Rua Exemplo',
            'address_number':'10','address_complement':'',
            'address_neighborhood':'Centro','address_city':'Rio de Janeiro','address_state':'RJ',
        }

    def test_public_registration_creates_only_online_account(self):
        from .models import PatientProfile, PortalAccount
        response=self.client.post(reverse('patient_register'),self.portal_data())
        self.assertRedirects(response,reverse('patient_complete_registration'))
        person=User.objects.get(email='pessoa@example.com')
        self.assertTrue(PortalAccount.objects.filter(user=person,phone='21999999999').exists())
        self.assertFalse(PatientProfile.objects.filter(user=person).exists())
        self.assertFalse(person.patient_verified)
        self.assertFalse(person.is_staff)
        self.assertFalse(person.is_superuser)
        self.assertContains(self.client.get(reverse('patient_complete_registration')),'Complete seu cadastro')
        from .forms import PatientRegisterForm
        self.assertNotIn('cpf',PatientRegisterForm().fields)
        self.assertNotIn('birth_date',PatientRegisterForm().fields)
    def test_public_signup_rejects_invalid_phone(self):
        data=self.portal_data();data['phone']='123'
        response=self.client.post(reverse('patient_register'),data)
        self.assertContains(response,'celular com DDD')
        self.assertFalse(User.objects.filter(email=data['email']).exists())

    def test_no_public_access_to_internal_pec_profile(self):
        patient=User.objects.create_user('p','new@example.com','SafeLongPassword123456',role=User.PATIENT)
        self.client.force_login(patient)
        url=reverse('staff_patient_clinical',kwargs={'user_id':patient.id})
        self.assertEqual(self.client.get(url).status_code,403)
        self.assertEqual(self.client.post(url,self.clinical_data()).status_code,403)
        from .models import PatientProfile
        self.assertFalse(PatientProfile.objects.filter(user=patient).exists())

    def test_reception_without_clinical_permission_cannot_view_medical_intake(self):
        patient=User.objects.create_user('p','new@example.com','SafeLongPassword123456',role=User.PATIENT)
        reception=User.objects.create_user('r','desk@example.com','SafeLongPassword123456',role=User.STAFF)
        self.client.force_login(reception)
        self.assertEqual(self.client.get(reverse('staff_patient_clinical',kwargs={'user_id':patient.id})).status_code,403)

    def test_clinical_staff_fills_internal_profile_without_verifying(self):
        from .models import PatientProfile
        patient=User.objects.create_user('p','new@example.com','SafeLongPassword123456',role=User.PATIENT)
        clinician=User.objects.create_user('c','clinician@example.com','SafeLongPassword123456',role=User.STAFF,clinical_access=True)
        self.client.force_login(clinician)
        url=reverse('staff_patient_clinical',kwargs={'user_id':patient.pk})
        self.assertContains(self.client.get(url),'Identificação do paciente')
        self.assertNotContains(self.client.get(url),'Condições de saúde autorreferidas')
        data=self.clinical_data();data['diabetes']='sim'
        response=self.client.post(url,data)
        self.assertEqual(response.status_code,302)
        profile=PatientProfile.objects.get(user=patient)
        self.assertEqual(profile.cpf,'52998224725')
        self.assertEqual(profile.birth_city,'Rio de Janeiro')
        self.assertEqual(profile.diabetes,'')
        self.assertEqual(profile.staff_updated_by,clinician)
        patient.refresh_from_db()
        self.assertFalse(patient.patient_verified)

    def test_legacy_health_data_is_preserved_when_updating_basic_registration(self):
        from .models import PatientProfile
        patient=User.objects.create_user('p','new@example.com','SafeLongPassword123456',role=User.PATIENT)
        clinician=User.objects.create_user('c','clinician@example.com','SafeLongPassword123456',role=User.STAFF,clinical_access=True)
        self.client.force_login(clinician)
        url=reverse('staff_patient_clinical',kwargs={'user_id':patient.pk})
        self.assertEqual(self.client.post(url,self.clinical_data()).status_code,302)
        profile=PatientProfile.objects.get(user=patient)
        profile.diabetes='sim'
        profile.educational_level='medio_completo'
        profile.save(update_fields=['diabetes','educational_level'])
        self.assertEqual(self.client.post(url,self.clinical_data()).status_code,302)
        profile.refresh_from_db()
        self.assertEqual(profile.diabetes,'sim')
        self.assertEqual(profile.educational_level,'medio_completo')
        response=self.client.get(url)
        self.assertNotContains(response,'Escolaridade')
        self.assertNotContains(response,'Diabetes autorreferido')

    def test_internal_form_does_not_request_unnecessary_sus_or_medical_details(self):
        from .forms import PatientClinicalIntakeForm
        fields=PatientClinicalIntakeForm().fields
        for excluded in ['cns','birth_record_number','father_name','blood_type','educational_level','employment','diabetes','pregnancy','smoking','race_color']:
            self.assertNotIn(excluded,fields)
        for required in ['cpf','birth_date','sex','mother_name','birth_city','birth_state','phone','postal_code','address_street','guardian_name']:
            self.assertIn(required,fields)

    def test_invalid_cpf_stays_only_in_internal_clinical_form(self):
        from .models import PatientProfile
        patient=User.objects.create_user('p','new@example.com','SafeLongPassword123456',role=User.PATIENT)
        clinician=User.objects.create_user('c','clinician@example.com','SafeLongPassword123456',role=User.STAFF,clinical_access=True)
        self.client.force_login(clinician)
        data=self.clinical_data();data['cpf']='111.111.111-11'
        response=self.client.post(reverse('staff_patient_clinical',kwargs={'user_id':patient.id}),data)
        self.assertContains(response,'CPF válido')
        self.assertFalse(PatientProfile.objects.filter(user=patient).exists())

    def test_cpf_absence_requires_justification_in_internal_intake(self):
        from .models import PatientProfile
        patient=User.objects.create_user('p','absent@example.com','SafeLongPassword123456',role=User.PATIENT)
        clinician=User.objects.create_user('c','clinician@example.com','SafeLongPassword123456',role=User.STAFF,clinical_access=True)
        self.client.force_login(clinician)
        url=reverse('staff_patient_clinical',kwargs={'user_id':patient.id})
        data=self.clinical_data();data['cpf']=''
        response=self.client.post(url,data)
        self.assertContains(response,'justificativa para não apresentar CPF')
        data['cpf_missing_reason']='Documento não apresentado no atendimento'
        response=self.client.post(url,data)
        self.assertEqual(response.status_code,302)
        self.assertIsNone(PatientProfile.objects.get(user=patient).cpf)

    def test_underage_intake_requires_guardian(self):
        from datetime import date
        patient=User.objects.create_user('p','new@example.com','SafeLongPassword123456',role=User.PATIENT)
        clinician=User.objects.create_user('c','clinician@example.com','SafeLongPassword123456',role=User.STAFF,clinical_access=True)
        self.client.force_login(clinician)
        d=self.clinical_data();d['birth_date']=date(2015,4,20).isoformat()
        response=self.client.post(reverse('staff_patient_clinical',kwargs={'user_id':patient.id}),d)
        self.assertContains(response,'responsável legal')

    def test_admin_cannot_verify_without_internal_profile(self):
        patient=User.objects.create_user('p','new@example.com','SafeLongPassword123456',role=User.PATIENT)
        admin=User.objects.create_superuser('a','admin@example.com','BootTempPass!123456')
        self.client.force_login(admin)
        response=self.client.post(reverse('verify_patient',kwargs={'user_id':patient.id}),{'identity_confirmed':'yes'})
        self.assertEqual(response.status_code,302)
        patient.refresh_from_db()
        self.assertFalse(patient.patient_verified)

    def test_patient_cannot_access_clinical_protocols(self):
        patient=User.objects.create_user('p','user-p@example.com','SafeLongPassword123456',role=User.PATIENT)
        self.client.force_login(patient)
        self.assertEqual(self.client.get(reverse('protocol_catalog')).status_code,403)
        self.client.logout()
        staff=User.objects.create_user('staff','staff-p@example.com','SafeLongPassword123456',role=User.STAFF)
        self.client.force_login(staff)
        response=self.client.get(reverse('protocol_catalog'))
        self.assertContains(response,'Mounjaro')
        self.assertContains(response,'Eli Lilly')
        self.assertEqual(response.context['protocols'].count(),29)

    def test_bootstrap_password_requires_rotation(self):
        from django.contrib.auth import authenticate
        admin=User.objects.create_superuser('m','m@example.com','BootTempPass!123456',must_change_password=True)
        self.client.force_login(admin)
        self.assertRedirects(self.client.get(reverse('staff_home')),reverse('master_change_password'))
        response=self.client.post(reverse('master_change_password'),{
            'old_password':'BootTempPass!123456',
            'new_password1':'BootNeverReuseStrong!1234',
            'new_password2':'BootNeverReuseStrong!1234',
        })
        self.assertRedirects(response,reverse('staff_home'))
        admin.refresh_from_db()
        self.assertFalse(admin.must_change_password)
        self.assertTrue(admin.check_password('BootNeverReuseStrong!1234'))

class InstitutionalNavigationTests(TestCase):
    """The public institutional tabs are independent, usable and do not expose portal data."""
    def test_five_tabs_have_independent_public_pages(self):
        routes = {
            'home': 'Cuidado que',
            'about': 'uma jornada de cuidado',
            'services': 'Saúde metabólica',
            'content': 'Metabolismo: olhar além da balança',
            'contact': '98819-3497',
        }
        for name, heading in routes.items():
            with self.subTest(page=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, heading)
                self.assertContains(response, 'aria-current="page"', count=0 if name == 'content' else 2)  # Screenshot navbar omits Conteúdos; available in footer
                self.assertContains(response, reverse('patient_login'))
                self.assertContains(response, reverse('staff_login'))

    def test_all_public_tabs_available_from_every_site_page(self):
        response = self.client.get(reverse('services'))
        for name in ('home', 'about', 'services', 'content', 'contact'):
            self.assertContains(response, f'href="{reverse(name)}"')
        self.assertContains(response, 'Navegação para celular')

    def test_public_navigation_does_not_change_portal_protection(self):
        self.assertRedirects(
            self.client.get(reverse('staff_home')),
            f'{reverse("staff_login")}?next={reverse("staff_home")}',
        )
        self.assertRedirects(
            self.client.get(reverse('patient_home')),
            f'{reverse("patient_login")}?next={reverse("patient_home")}',
        )


class OfficialContactsAndLocationsTests(TestCase):
    """Public contact is informative and never assigns another business address to Alegre."""
    def test_contact_displays_both_addresses_and_embedded_maps(self):
        page = self.client.get(reverse('contact'))
        self.assertEqual(page.status_code, 200)
        for val in ('Cesário de Melo, 2855', 'Salas 705 e 706', '23052-101', 'Alegre/ES', 'Spazio Center', 'Jerônimo Monteiro, 113', 'Sala 10', '29500-000'):
            self.assertContains(page, val)
        self.assertContains(page, '5521988193497')
        self.assertContains(page, 'lombardisaude@gmail.com')
        self.assertContains(page, '@lombardi.saude')
        self.assertContains(page, 'google.com/maps/search/', count=4)
        self.assertContains(page, 'google.com/maps?q=', count=2)
        self.assertContains(page, 'output=embed', count=2)
        self.assertContains(page, '@lombardi.saude', count=2)

    def test_every_page_shows_localities_in_footer(self):
        for route in ('home', 'about', 'services', 'content', 'contact'):
            with self.subTest(route=route):
                response=self.client.get(reverse(route))
                self.assertContains(response, 'Campo Grande/RJ')
                self.assertContains(response, 'Alegre/ES')
                self.assertContains(response, 'v0.7.6')

    def test_contact_does_not_expose_patient_data(self):
        page=self.client.get(reverse('contact'))
        self.assertNotContains(page, 'clinical_access')
        self.assertNotContains(page, 'patient_verified')
        self.assertEqual(self.client.get(reverse('staff_home')).status_code, 302)


class EditorialLandingTests(TestCase):
    def test_home_has_reference_sections(self):
        response=self.client.get(reverse('home'))
        self.assertEqual(response.status_code,200)
        for item in ['Cuidado que','transforma vidas','Conhecimento, experiência','Saúde em todas as fases','Área do Paciente','Área Profissional']:
            self.assertContains(response,item)
        for page in ['specialties','technology','about','services','contact']:
            self.assertIn(reverse(page),response.content.decode())

    def test_specialties_and_technology_are_distinct_pages(self):
        self.assertContains(self.client.get(reverse('specialties')),'Controle de Peso e Metabolismo')
        self.assertContains(self.client.get(reverse('technology')),'Decisões baseadas em evidências')

    def test_landing_does_not_remove_private_portal_protection(self):
        self.assertRedirects(self.client.get(reverse('staff_home')),reverse('staff_login')+'?next='+reverse('staff_home'))

    def test_appointment_link_still_requires_patient_session(self):
        self.assertRedirects(self.client.get(reverse('book')),reverse('patient_login')+'?next='+reverse('book'))


class OfficialBrandingTests(TestCase):
    def test_official_logo_is_used_in_header_and_footer(self):
        for route in ('home','about','services','specialties','contact','patient_login','staff_login'):
            with self.subTest(route=route):
                response=self.client.get(reverse(route))
                self.assertContains(response, 'img/lombardi-logo-transparente.webp', count=2)
                self.assertNotContains(response, '<span class="lx-logo-mark"')
                self.assertContains(response, 'Lombardi Saúde — Seja a sua melhor versão')


class ProductionDemoSafetyTests(TestCase):
    def setUp(self):
        self.user=User.objects.create_user('demo-paciente-lombardi','paciente.teste@example.com','TestOnlySafeLongPass-2026',role=User.PATIENT,patient_verified=False)
        self.client.force_login(self.user)

    def test_demo_cannot_book_appointments(self):
        self.assertEqual(self.client.get(reverse('patient_home')).status_code,200)
        self.assertContains(self.client.get(reverse('patient_home')),'CONTA DE TESTE')
        self.assertRedirects(self.client.post(reverse('book'),{'slot_id':'99999'}),reverse('book'))
        self.assertEqual(Appointment.objects.count(),0)

    def test_demo_cannot_request_invoices(self):
        self.assertRedirects(self.client.post(reverse('request_invoice'),{}),reverse('my_invoices'))
        self.assertEqual(InvoiceRequest.objects.count(),0)

    def test_demo_is_not_clinically_verified(self):
        self.assertFalse(self.user.patient_verified)
        self.assertEqual(self.client.get(reverse('my_records')).status_code,200)

class CatalogIndividualizationTests(TestCase):
    def test_clinical_protocols_are_not_auto_indicated(self):
        u=User.objects.create_user('staff-clinic','staff-test@example.com','TestOnlySafeLongPass-2026',role=User.STAFF)
        self.client.force_login(u)
        r=self.client.get(reverse('protocol_catalog'))
        self.assertContains(r,'AVALIAÇÃO INDIVIDUAL OBRIGATÓRIA')
        self.assertContains(r,'Não existe indicação automática')

class MasterAccessTests(TestCase):
    def test_master_dashboard_link(self):
        u=User.objects.create_superuser('master-test','admin-test@example.com','TestOnlySafeLongPass-2026')
        self.client.force_login(u)
        self.assertContains(self.client.get(reverse('staff_home')),'Administração da clínica')
        self.assertEqual(self.client.get('/gestao/').status_code,200)


class PrivatePdfDeliveryTests(TestCase):
    """Receitas e dietas: upload e download exigem identidade e permissão clínica."""
    PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n"

    def setUp(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        self.patient = User.objects.create_user("pdf-patient", "pdf-patient@example.com", "ClinicTestPassword!1234", role=User.PATIENT, patient_verified=True)
        self.other = User.objects.create_user("pdf-other", "pdf-other@example.com", "ClinicTestPassword!1234", role=User.PATIENT, patient_verified=True)
        self.clinician = User.objects.create_user("pdf-doctor", "pdf-doctor@example.com", "ClinicTestPassword!1234", role=User.STAFF, clinical_access=True)
        self.staff = User.objects.create_user("pdf-reception", "pdf-reception@example.com", "ClinicTestPassword!1234", role=User.STAFF)
        self.finance = User.objects.create_user("pdf-finance", "pdf-finance@example.com", "ClinicTestPassword!1234", role=User.STAFF, financial_access=True)
        self.upload = lambda content=None: SimpleUploadedFile("receita.pdf", self.PDF if content is None else content, content_type="application/pdf")

    def test_patient_home_shows_new_sections_instead_of_prontuario(self):
        self.client.force_login(self.patient)
        resp = self.client.get(reverse("patient_home"))
        self.assertContains(resp, "Minhas Receitas")
        self.assertContains(resp, "Minhas Dietas")
        self.assertNotContains(resp, '<h3>Prontuário</h3>')
        self.assertEqual(self.client.get(reverse("my_documents", kwargs={"kind": "diet"})).status_code, 200)
        self.assertEqual(self.client.get(reverse("my_documents", kwargs={"kind": "invalid"})).status_code, 404)

    def test_clinician_can_upload_both_kinds_and_patient_is_notified(self):
        from .models import PatientDocument, AuditEvent
        for kind in (PatientDocument.PRESCRIPTION, PatientDocument.DIET):
            with self.subTest(kind=kind):
                self.client.force_login(self.clinician)
                url = reverse("staff_patient_documents", kwargs={"user_id": self.patient.id, "kind": kind})
                resp = self.client.post(url, {"title": "Documento teste " + kind, "document": self.upload(), **({"transcription": "Uso conforme receita original de teste.\nResponsável: profissional.", "confirmed_transcription": "on"} if kind == PatientDocument.PRESCRIPTION else {})})
                self.assertRedirects(resp, url)
                doc = PatientDocument.objects.get(patient=self.patient, kind=kind)
                self.assertEqual(bytes(doc.document_pdf), self.PDF)
                self.assertTrue(AuditEvent.objects.filter(action="patient_document_uploaded",reference_id=str(doc.pk)).exists())
                self.assertTrue(Notification.objects.filter(recipient=self.patient,category=kind + "_ready").exists())
                self.client.force_login(self.patient)
                self.assertContains(self.client.get(reverse("my_documents", kwargs={"kind": kind})), doc.title)
                download = self.client.get(reverse("download_document", kwargs={"document_id":doc.pk}))
                self.assertEqual(download.status_code,200)
                self.assertEqual(download.content,self.PDF)
                self.assertEqual(download["Cache-Control"],"private, no-store")

    def test_pdf_is_private_and_staff_permissions_enforced(self):
        from .models import PatientDocument
        doc = PatientDocument.objects.create(patient=self.patient,kind=PatientDocument.DIET,title="Plano privado",document_pdf=self.PDF,uploaded_by=self.clinician)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse("download_document",kwargs={"document_id":doc.id})).status_code,404)
        self.client.force_login(self.staff)
        for name in ("staff_download_document", "staff_archive_document"):
            self.assertEqual((self.client.get if name=="staff_download_document" else self.client.post)(reverse(name,kwargs={"document_id":doc.id})).status_code,403)
        self.assertEqual(self.client.get(reverse("staff_patient_documents",kwargs={"user_id":self.patient.id,"kind":"diet"})).status_code,403)
        self.client.force_login(self.finance)
        self.assertEqual(self.client.get(reverse("staff_download_document",kwargs={"document_id":doc.id})).status_code,403)
        self.client.force_login(self.clinician)
        self.assertEqual(self.client.get(reverse("staff_download_document",kwargs={"document_id":doc.id})).status_code,200)
        self.assertRedirects(self.client.post(reverse("staff_archive_document",kwargs={"document_id":doc.id})),reverse("staff_patient_documents",kwargs={"user_id":self.patient.id,"kind":"diet"}))
        self.client.force_login(self.patient)
        self.assertEqual(self.client.get(reverse("download_document",kwargs={"document_id":doc.id})).status_code,404)

    def test_bad_upload_rejected_and_unverified_patient_cannot_receive_pdf(self):
        from .models import PatientDocument
        self.client.force_login(self.clinician)
        url = reverse("staff_patient_documents",kwargs={"user_id":self.patient.id,"kind":"prescription"})
        resp=self.client.post(url,{"title":"Incorreto","document":self.upload(b"not-a-pdf"),"transcription":"Teste original","confirmed_transcription":"on"})
        self.assertEqual(resp.status_code,200)
        self.assertContains(resp,"Arquivo inválido")
        self.assertEqual(PatientDocument.objects.count(),0)
        self.patient.patient_verified=False
        self.patient.save(update_fields=["patient_verified"])
        resp=self.client.post(url,{"title":"Bloqueado","document":self.upload()})
        self.assertEqual(resp.status_code,302)
        self.assertEqual(PatientDocument.objects.count(),0)
        self.client.force_login(self.patient)
        self.assertEqual(self.client.get(reverse("download_document",kwargs={"document_id":"00000000-0000-0000-0000-000000000001"})).status_code,403)

    def test_demo_patient_never_gets_clinical_pdfs(self):
        demo = User.objects.create_user("demo-paciente-lombardi","demo-private@example.com","ClinicTestPassword!1234",role=User.PATIENT,patient_verified=True)
        self.client.force_login(self.clinician)
        self.assertEqual(self.client.get(reverse("staff_patient_documents",kwargs={"user_id":demo.id,"kind":"diet"})).status_code,403)
        self.client.force_login(demo)
        self.assertContains(self.client.get(reverse("my_documents",kwargs={"kind":"diet"})),"Conta de demonstração")


class NotificationBellTests(TestCase):
    """The only notification UI is the scoped bell in the portal header."""

    def setUp(self):
        self.patient = User.objects.create_user('bellpatient', 'bellpatient@example.com', 'StrongPassword!666', role=User.PATIENT)
        self.other = User.objects.create_user('bellother', 'bellother@example.com', 'StrongPassword!667', role=User.PATIENT)
        self.staff = User.objects.create_user('bellstaff', 'bellstaff@example.com', 'StrongPassword!668', role=User.STAFF)
        self.own = Notification.objects.create(recipient=self.patient, category='invoice_update', title='Sua nota fiscal', message='O documento está disponível.', link='/paciente/notas/')
        self.other_notice = Notification.objects.create(recipient=self.other, category='exam', title='Dados privados da outra conta', message='Não pode aparecer para o paciente principal.', link='/paciente/exames/')
        self.staff_notice = Notification.objects.create(recipient=self.staff, category='staff_booking', title='Nova consulta', message='Consulta em aberto.', link='/funcionario/')

    def test_anonymous_site_has_no_bell(self):
        response = self.client.get(reverse('home'))
        self.assertNotContains(response, 'lombardi-notification-bell')
        self.assertNotContains(response, 'Sua nota fiscal')

    def test_patient_bell_only_contains_own_notifications(self):
        self.client.force_login(self.patient)
        response = self.client.get(reverse('patient_home'))
        self.assertContains(response, 'lombardi-notification-bell')
        self.assertContains(response, 'Sua nota fiscal')
        self.assertContains(response, '1 não lida')
        self.assertNotContains(response, 'Dados privados da outra conta')
        self.assertNotContains(response, 'Central de notificações')

    def test_staff_bell_only_contains_staff_notifications(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse('staff_home'))
        self.assertContains(response, 'lombardi-notification-bell')
        self.assertContains(response, 'Nova consulta')
        self.assertNotContains(response, 'Sua nota fiscal')

    def test_one_notification_mark_requires_post_and_ownership(self):
        self.client.force_login(self.patient)
        own_url = reverse('notification_read', kwargs={'notification_id': self.own.pk})
        self.assertEqual(self.client.get(own_url).status_code, 405)
        res = self.client.post(own_url, {'return_to': reverse('patient_home')})
        self.assertEqual(res.status_code, 302)
        self.assertIn('notificacoes=1', res['Location'])
        self.own.refresh_from_db()
        self.assertIsNotNone(self.own.read_at)
        res = self.client.post(reverse('notification_read', kwargs={'notification_id': self.other_notice.pk}))
        self.assertEqual(res.status_code, 404)
        self.assertIsNone(Notification.objects.get(pk=self.other_notice.pk).read_at)

    def test_mark_all_only_changes_own_unread(self):
        self.client.force_login(self.patient)
        res = self.client.post(reverse('notifications_read_all'), {'return_to': 'https://evil.example/steal'})
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res['Location'], '/paciente/?notificacoes=1')
        self.own.refresh_from_db()
        self.other_notice.refresh_from_db()
        self.assertIsNotNone(self.own.read_at)
        self.assertIsNone(self.other_notice.read_at)

    def test_open_marks_read_redirects_internally_only(self):
        self.client.force_login(self.patient)
        res = self.client.post(reverse('notification_open', kwargs={'notification_id': self.own.pk}))
        self.assertRedirects(res, reverse('my_invoices'), fetch_redirect_response=False)
        self.own.refresh_from_db()
        self.assertIsNotNone(self.own.read_at)
        self.own.link = '//evil.example/trap'
        self.own.save(update_fields=['link'])
        res = self.client.post(reverse('notification_open', kwargs={'notification_id': self.own.pk}))
        self.assertRedirects(res, reverse('patient_home'), fetch_redirect_response=False)

    def test_paging_shows_all_own_notifications_and_no_other_records(self):
        for i in range(40):
            Notification.objects.create(recipient=self.patient, title=f'Evento {i:02}', category='test', message='Mensagem')
        self.client.force_login(self.patient)
        first = self.client.get(reverse('patient_home'))
        self.assertContains(first, 'Carregar notificações anteriores')
        response = self.client.get(reverse('notifications_more'), {'offset': 12})
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(len(result['items']), 20)
        self.assertTrue(result['has_more'])
        self.assertFalse(any(v['title'] == 'Dados privados da outra conta' for v in result['items']))
        final = self.client.get(reverse('notifications_more'), {'offset': 32}).json()
        self.assertEqual(len(final['items']), 9)
        self.assertFalse(final['has_more'])
        self.assertEqual(self.client.get(reverse('notifications_more'), {'offset': '-4'}).status_code, 400)

    def test_legacy_notifications_page_redirects_to_bell(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse('notifications'))
        self.assertRedirects(response, '/funcionario/?notificacoes=1', fetch_redirect_response=False)


class PrescriptionTranscriptionAndNotificationsTests(TestCase):
    """A leitura pode ser transcrita; a impressão deve usar o PDF original, privadamente."""
    PDF = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n"

    def setUp(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        self.patient = User.objects.create_user("recipe-patient", "rp@example.com", "StrongSecurePass!123", role=User.PATIENT, patient_verified=True)
        self.other = User.objects.create_user("recipe-other", "ro@example.com", "StrongSecurePass!123", role=User.PATIENT, patient_verified=True)
        self.clinician = User.objects.create_user("recipe-clinician", "rc@example.com", "StrongSecurePass!123", role=User.STAFF, clinical_access=True)
        self.reception = User.objects.create_user("recipe-reception", "rr@example.com", "StrongSecurePass!123", role=User.STAFF)
        self.finance = User.objects.create_user("recipe-finance", "rf@example.com", "StrongSecurePass!123", role=User.STAFF, financial_access=True)
        self.SimpleUploadedFile = SimpleUploadedFile

    def upload_recipe(self, transcription, confirmation="on"):
        form = {"title": "Receita da consulta", "document": self.SimpleUploadedFile("receita-original.pdf", self.PDF, content_type="application/pdf"),
                "transcription": transcription, "confirmed_transcription": confirmation}
        return self.client.post(reverse("staff_patient_documents", kwargs={"user_id": self.patient.pk, "kind": "prescription"}), form)

    def test_manual_transcription_is_required_and_must_be_confirmed(self):
        from .models import PatientDocument
        self.client.force_login(self.clinician)
        res = self.upload_recipe("", "on")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(PatientDocument.objects.count(), 0)
        res = self.upload_recipe("Tomar conforme receita original", "")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(PatientDocument.objects.count(), 0)
        res = self.upload_recipe("Tomar conforme receita original", "on")
        self.assertEqual(res.status_code, 302)
        doc = PatientDocument.objects.get()
        self.assertEqual(doc.transcription, "Tomar conforme receita original")
        self.assertEqual(bytes(doc.document_pdf), self.PDF)
        self.assertTrue(Notification.objects.filter(recipient=self.patient, category="prescription_ready").exists())

    def test_patient_reads_text_but_prints_original_pdf_only(self):
        from .models import PatientDocument, AuditEvent
        doc = PatientDocument.objects.create(patient=self.patient, kind=PatientDocument.PRESCRIPTION,
            title="Receita 01", transcription="Uso com orientação profissional.\nDuração conforme original.", document_pdf=self.PDF, uploaded_by=self.clinician)
        self.client.force_login(self.patient)
        response = self.client.get(reverse('my_documents',kwargs={'kind':'prescription'}))
        self.assertContains(response, 'Uso com orientação profissional.')
        self.assertContains(response, 'Duração conforme original.')
        self.assertContains(response, 'Imprimir receita original (PDF)')
        original = self.client.get(reverse('print_original_prescription', kwargs={'document_id':doc.id}))
        self.assertEqual(original.status_code, 200)
        self.assertEqual(original.content, self.PDF)
        self.assertTrue(original['Content-Disposition'].startswith('inline;'))
        self.assertEqual(original['Cache-Control'],'private, no-store')
        self.assertTrue(AuditEvent.objects.filter(action='patient_prescription_original_print', reference_id=str(doc.pk)).exists())
        self.assertEqual(self.client.get(reverse('download_document',kwargs={'document_id':doc.id})).content, self.PDF)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse('print_original_prescription',kwargs={'document_id':doc.id})).status_code,404)
        self.client.force_login(self.reception)
        self.assertEqual(self.client.get(reverse('print_original_prescription',kwargs={'document_id':doc.id})).status_code,403)

    def test_legacy_recipe_no_fabricated_transcription_and_no_diet_print(self):
        from .models import PatientDocument
        legacy = PatientDocument.objects.create(patient=self.patient, kind=PatientDocument.PRESCRIPTION,
           title="Receita anterior", document_pdf=self.PDF,uploaded_by=self.clinician)
        diet = PatientDocument.objects.create(patient=self.patient, kind=PatientDocument.DIET,
           title="Dieta", document_pdf=self.PDF, uploaded_by=self.clinician)
        self.client.force_login(self.patient)
        self.assertContains(self.client.get(reverse('my_documents',kwargs={'kind':'prescription'})), 'transcrição ainda não foi disponibilizada')
        self.assertEqual(self.client.get(reverse('print_original_prescription',kwargs={'document_id':legacy.pk})).content,self.PDF)
        self.assertEqual(self.client.get(reverse('print_original_prescription',kwargs={'document_id':diet.pk})).status_code,404)

    def test_transcribed_html_is_escaped(self):
        from .models import PatientDocument
        PatientDocument.objects.create(patient=self.patient, kind=PatientDocument.PRESCRIPTION,
           title="Documento de teste",transcription="<script>alert('x')</script>",document_pdf=self.PDF,uploaded_by=self.clinician)
        self.client.force_login(self.patient)
        response=self.client.get(reverse('my_documents',kwargs={'kind':'prescription'}))
        self.assertNotContains(response, "<script>alert('x')</script>")
        self.assertContains(response, '&lt;script&gt;', html=False)

    def test_patient_registration_and_contact_change_reach_staff_bell(self):
        from .models import PortalAccount
        self.client.logout()
        response=self.client.post(reverse('patient_register'),{
            'name':'Paciente de Teste','email':'novo-cadastro@example.com','phone':'21999999999',
            'password':'StrongNewPassword!1234','password_confirm':'StrongNewPassword!1234','privacy_acknowledgement':'on'})
        self.assertEqual(response.status_code,302)
        notice=Notification.objects.filter(recipient=self.reception,category='patient_registration').first()
        self.assertIsNotNone(notice)
        self.assertEqual(notice.link,reverse('staff_patient_search'))
        self.client.force_login(User.objects.get(email='novo-cadastro@example.com'))
        account=PortalAccount.objects.get(user__email='novo-cadastro@example.com')
        response=self.client.post(reverse('patient_complete_registration'),{
            'cpf':'52998224725', 'birth_date':'1990-03-10','sex':'F','race_color':'nao_informada',
            'mother_name':'Ana de Teste','nationality':'brasileira',
            'birth_country':'Brasil','birth_state':'RJ','birth_city':'Rio de Janeiro',
            'phone':'21999999999','postal_code':'23000000','address_street':'Rua Exemplo',
            'address_number':'10','address_neighborhood':'Centro',
            'address_city':'Rio de Janeiro','address_state':'RJ','data_awareness':'on',
        })
        self.assertEqual(response.status_code,302)
        response=self.client.post(reverse('patient_profile'),{'phone':'21988888888'})
        self.assertEqual(response.status_code,302)
        self.assertTrue(Notification.objects.filter(recipient=self.reception,category='patient_contact_update').exists())

    def test_invoice_request_goes_only_to_finance_and_master(self):
        seed_legacy_fiscal_fixture(self.patient)
        master = User.objects.create_superuser('recipe-admin','rm@example.com','StrongSecurePass!123')
        self.client.force_login(self.patient)
        response=self.client.post(reverse('request_invoice'))
        self.assertEqual(response.status_code,302)
        self.assertTrue(Notification.objects.filter(recipient=self.finance,category='invoice_requested').exists())
        self.assertTrue(Notification.objects.filter(recipient=master,category='invoice_requested').exists())
        self.assertFalse(Notification.objects.filter(recipient=self.reception,category='invoice_requested').exists())
        self.assertTrue(Notification.objects.filter(recipient=self.patient,category='invoice_requested').exists())


class DepartmentAccessAndProtocolTests(TestCase):
    """Operational reception visibility is read-only; clinical content is restricted."""
    def setUp(self):
        from .models import Protocol
        self.patient = User.objects.create_user('ptdept', 'ptdept@example.com', 'StrongPass#patient21', role=User.PATIENT, patient_verified=True)
        self.other = User.objects.create_user('otherdept', 'otherdept@example.com', 'StrongPass#other21', role=User.PATIENT, patient_verified=True)
        self.doctor = User.objects.create_user('docdept','docdept@example.com','StrongPass#doctor21',role=User.STAFF,staff_job=User.JOB_DOCTOR)
        self.nurse = User.objects.create_user('nursedept','nursedept@example.com','StrongPass#nurse21',role=User.STAFF,staff_job=User.JOB_NURSE)
        self.technician = User.objects.create_user('techdept','techdept@example.com','StrongPass#tech21',role=User.STAFF,staff_job=User.JOB_TECH)
        self.finance = User.objects.create_user('findept','findept@example.com','StrongPass#finance21',role=User.STAFF,staff_job=User.JOB_FINANCE)
        self.reception = User.objects.create_user('recdept','recdept@example.com','StrongPass#reception21',role=User.STAFF,staff_job=User.JOB_RECEPTION)
        self.protocol = Protocol.objects.create(name='Protocolo de teste individualizado',category=Protocol.CARE,description='Apenas demonstração',active=True)

    def prescribe(self):
        from .models import PatientProtocol
        return PatientProtocol.objects.create(patient=self.patient,protocol=self.protocol,
            prescribed_by=self.doctor,clinical_justification='Necessidade individual avaliada pelo médico responsável.',
            instructions='Conforme avaliação clínica.')

    def test_doctor_assigns_protocol_and_notifies_patient(self):
        from .models import PatientProtocol
        self.client.force_login(self.doctor)
        resp=self.client.post(reverse('staff_add_patient_protocol',kwargs={'user_id':self.patient.pk}),{
            'protocol':self.protocol.pk,'clinical_justification':'Necessidade individual clinicamente documentada.',
            'instructions':'Orientação de acompanhamento','clinical_confirmation':'on'})
        self.assertRedirects(resp,reverse('staff_protocol_queue'))
        self.assertEqual(PatientProtocol.objects.filter(patient=self.patient).count(),1)
        self.assertTrue(Notification.objects.filter(recipient=self.patient,category='protocol_assigned').exists())

    def test_protocol_requires_justification_and_confirmation(self):
        from .models import PatientProtocol
        self.client.force_login(self.doctor)
        url=reverse('staff_add_patient_protocol',kwargs={'user_id':self.patient.pk})
        response=self.client.post(url,{'protocol':self.protocol.pk,'clinical_justification':'', 'clinical_confirmation':''})
        self.assertEqual(response.status_code,200)
        self.assertEqual(PatientProtocol.objects.count(),0)

    def test_staff_department_permissions_matrix(self):
        from .models import PatientProtocol
        order=self.prescribe()
        urls={'queue':reverse('staff_protocol_queue'),'reception':reverse('reception_overview'),
              'finance':reverse('staff_invoices'),
              'prescribe':reverse('staff_add_patient_protocol',kwargs={'user_id':self.patient.id}),
              'recipe':reverse('staff_patient_documents',kwargs={'user_id':self.patient.id,'kind':'prescription'})}
        permissions=[(self.doctor,[200,403,403,200,200]),
                     (self.nurse,[200,403,403,403,403]),
                     (self.technician,[200,403,403,403,403]),
                     (self.finance,[403,403,200,403,403]),
                     (self.reception,[200,200,403,403,403])]
        for person,status in permissions:
            with self.subTest(user=person.username):
                self.client.force_login(person)
                got=[self.client.get(u).status_code for u in urls.values()]
                self.assertEqual(got,status)
        self.client.force_login(self.nurse)
        self.assertEqual(self.client.post(reverse('staff_protocol_update',kwargs={'protocol_id':order.id}),{'status':'performed'}).status_code,403)
        order.refresh_from_db()
        self.assertEqual(order.status,PatientProtocol.PENDING)

    def test_reception_sees_every_sectors_backlog_without_medical_details(self):
        from .models import ExamOrder, InvoiceRequest
        self.prescribe()
        InvoiceRequest.objects.create(patient=self.patient)
        ExamOrder.objects.create(patient=self.patient,author=self.doctor,title='Exame clínico privado',instructions='Dados altamente sensíveis')
        self.client.force_login(self.reception)
        response=self.client.get(reverse('reception_overview'))
        self.assertContains(response,'Enfermagem')
        self.assertContains(response,'Financeiro')
        self.assertContains(response,'Médico')
        self.assertContains(response,'Recepção')
        self.assertContains(response,self.patient.get_full_name() or self.patient.email)
        self.assertNotContains(response,'Dados altamente sensíveis')
        self.assertNotContains(response,'Necessidade individual avaliada')
        self.assertNotContains(response,'Exame clínico privado')
        self.assertEqual(self.client.get(reverse('staff_invoices')).status_code,403)

    def test_reception_receives_invoice_notification_but_cannot_issue_invoice(self):
        seed_legacy_fiscal_fixture(self.patient)
        self.client.force_login(self.patient)
        self.assertEqual(self.client.post(reverse('request_invoice')).status_code,302)
        self.assertTrue(Notification.objects.filter(recipient=self.reception,category='invoice_requested').exists())
        self.client.force_login(self.reception)
        self.assertEqual(self.client.get(reverse('reception_overview')).status_code,200)

    def test_patient_only_sees_own_protocol_and_not_demo(self):
        self.prescribe()
        self.client.force_login(self.patient)
        self.assertContains(self.client.get(reverse('my_protocols')),self.protocol.name)
        self.client.force_login(self.other)
        self.assertNotContains(self.client.get(reverse('my_protocols')),self.protocol.name)

    def test_protocol_completed_only_by_doctor(self):
        from .models import PatientProtocol
        row=self.prescribe()
        self.client.force_login(self.doctor)
        self.assertRedirects(self.client.post(reverse('staff_protocol_update',kwargs={'protocol_id':row.id}),{'status':'performed'}),reverse('staff_protocol_queue'))
        row.refresh_from_db()
        self.assertEqual(row.status,PatientProtocol.PERFORMED)
        self.assertTrue(Notification.objects.filter(recipient=self.patient,category='protocol_status').exists())

    def test_patient_can_read_protocol_status_but_never_clinical_justification(self):
        self.prescribe()
        self.client.force_login(self.patient)
        response=self.client.get(reverse('my_protocols'))
        self.assertContains(response,'A realizar')
        self.assertNotContains(response,'Necessidade individual avaliada pelo médico responsável.')

class FullRegistrationAndFiscalBillingTests(TestCase):
    """LGPD: campos sensíveis opcionais, dados fiscais restritos e cadastro obrigatório."""
    def setUp(self):
        from .models import PortalAccount
        self.patient = User.objects.create_user('fiscaluser','cliente-fiscal@example.com','A-secure-password12345!',role=User.PATIENT,first_name='Paciente Fiscal')
        PortalAccount.objects.create(user=self.patient, phone='21999999999', privacy_acknowledged_at=timezone.now())
        self.finance = User.objects.create_user('financeinvoice','fiscal-team@example.com','A-secure-password12345!', role=User.STAFF, staff_job=User.JOB_FINANCE)
        self.reception = User.objects.create_user('receptioninvoice','recepcao-team@example.com','A-secure-password12345!', role=User.STAFF, staff_job=User.JOB_RECEPTION)

    def complete_form(self):
        return {
            'cpf':'529.982.247-25', 'cpf_missing_reason':'', 'social_name':'',
            'birth_date':'1991-10-17', 'sex':'F', 'race_color':'', 'mother_name':'Ana Santos', 'mother_unknown':'',
            'nationality':'brasileira', 'birth_country':'Brasil', 'birth_state':'RJ', 'birth_city':'Rio de Janeiro',
            'phone':'21999999999', 'postal_code':'23052101', 'address_street':'Av. Cesário de Melo',
            'address_number':'2855', 'address_neighborhood':'Campo Grande', 'address_city':'Rio de Janeiro', 'address_state':'RJ',
            'data_awareness':'on',
        }

    def test_after_signup_account_redirects_to_complete_form(self):
        self.client.force_login(self.patient)
        self.assertRedirects(self.client.get(reverse('patient_home')),reverse('patient_complete_registration'))
        for route in ('book','my_invoices','my_protocols'):
            self.assertRedirects(self.client.get(reverse(route)),reverse('patient_complete_registration'))
        resp = self.client.get(reverse('patient_complete_registration'))
        self.assertContains(resp, 'inspirado na estrutura do PEC e-SUS APS')
        self.assertContains(resp,'Dados sociais opcionais')
        self.assertContains(resp,'Condições de saúde autorreferidas')

    def test_full_registration_creates_record_with_optional_sensitive_fields(self):
        from .models import PatientProfile
        self.client.force_login(self.patient)
        response=self.client.post(reverse('patient_complete_registration'),self.complete_form())
        self.assertRedirects(response,reverse('patient_home'))
        p=PatientProfile.objects.get(user=self.patient)
        self.assertEqual(p.cpf,'52998224725')
        self.assertEqual(p.race_color,'nao_informada')
        self.assertEqual(p.address_city,'Rio de Janeiro')
        self.assertIsNotNone(p.registration_completed_at)
        self.assertFalse(self.patient.patient_verified)
        self.assertEqual(self.client.get(reverse('patient_home')).status_code,200)

    def test_cpf_invalid_rejected_and_no_profile_created(self):
        from .models import PatientProfile
        self.client.force_login(self.patient)
        values=self.complete_form(); values['cpf']='111.111.111-11'
        response=self.client.post(reverse('patient_complete_registration'),values)
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'CPF válido')
        self.assertFalse(PatientProfile.objects.filter(user=self.patient).exists())

    def test_invoice_snapshot_shows_hour_name_cpf_and_billing_tab_only_to_finance(self):
        self.client.force_login(self.patient)
        self.assertRedirects(self.client.post(reverse('patient_complete_registration'),self.complete_form()),reverse('patient_home'))
        self.assertRedirects(self.client.post(reverse('request_invoice')),reverse('my_invoices'))
        invoice=InvoiceRequest.objects.get(patient=self.patient)
        self.assertEqual(invoice.billing_snapshot['cpf'],'52998224725')
        self.assertEqual(invoice.billing_snapshot['address_street'],'Av. Cesário de Melo')
        self.client.force_login(self.finance)
        page=self.client.get(reverse('staff_invoices'))
        self.assertContains(page,'Paciente Fiscal')
        self.assertContains(page,'529.982.247-25')
        self.assertContains(page,'Solicitação:')
        self.assertContains(page,'Dados para emissão')
        details=self.client.get(reverse('staff_invoice_billing_details',kwargs={'invoice_id':invoice.id}))
        self.assertContains(details,'Campo Grande')
        self.assertContains(details,'529.982.247-25')
        self.client.force_login(self.reception)
        self.assertEqual(self.client.get(reverse('staff_invoice_billing_details',kwargs={'invoice_id':invoice.id})).status_code,403)
        self.client.force_login(self.patient)
        self.assertEqual(self.client.get(reverse('staff_invoice_billing_details',kwargs={'invoice_id':invoice.id})).status_code,403)

    def test_billing_snapshot_remains_the_same_after_profile_updated(self):
        from .models import PatientProfile
        self.client.force_login(self.patient)
        self.client.post(reverse('patient_complete_registration'),self.complete_form())
        self.client.post(reverse('request_invoice'))
        invoice=InvoiceRequest.objects.get(patient=self.patient)
        profile=PatientProfile.objects.get(user=self.patient)
        profile.address_number='10'
        profile.save(update_fields=['address_number'])
        invoice.refresh_from_db()
        self.assertEqual(invoice.billing_data['address_number'],'2855')

    def test_invoice_with_no_cpf_is_blocked_even_if_registration_completed(self):
        values=self.complete_form()
        values['cpf']='';values['cpf_missing_reason']='Não possui CPF'
        self.client.force_login(self.patient)
        self.assertRedirects(self.client.post(reverse('patient_complete_registration'),values),reverse('patient_home'))
        self.assertRedirects(self.client.post(reverse('request_invoice')),reverse('patient_complete_registration'))
        self.assertFalse(InvoiceRequest.objects.filter(patient=self.patient).exists())
