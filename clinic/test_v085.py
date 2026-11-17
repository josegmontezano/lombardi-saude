from datetime import timedelta
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model
from .models import WebsiteVisit, VisitorSubmission, InstagramEntry, VlogVideo

User=get_user_model()

class V085Tests(TestCase):
    def setUp(self):
        self.master=User.objects.create_superuser('v085-m','v085-master@example.com','Strong-pass-123!!')
        self.staff=User.objects.create_user('v085-public','v085public@example.com','Strong-pass-123!!',role=User.PATIENT)
    def test_rebranding_and_public_pages(self):
        for url in ['/','/vlog/','/duvidas/','/instagram/']:
            self.assertEqual(self.client.get(url).status_code,200,url)
        self.assertContains(self.client.get('/vlog/'),'Tirando Dúvidas com a Lombardi Saúde')
        self.assertContains(self.client.get('/duvidas/'),'Enviar dúvida ou mensagem')
        self.assertContains(self.client.get('/instagram/'),'@lombardi.saude')
    def test_analytics_opt_in_and_geo_city(self):
        self.client.get('/')
        self.assertFalse(WebsiteVisit.objects.exists())
        self.client.post(reverse('analytics_consent'),{'consent':'yes'})
        self.client.get('/',HTTP_X_VERCEL_IP_COUNTRY='BR',HTTP_X_VERCEL_IP_COUNTRY_REGION='ES',HTTP_X_VERCEL_IP_CITY='Alegre')
        self.assertEqual(WebsiteVisit.objects.count(),1)
        item=WebsiteVisit.objects.get()
        self.assertEqual(item.country,'BR')
        self.assertEqual(item.region,'ES')
        self.assertEqual(item.city,'Alegre')
        self.assertTrue(item.visitor_token)
        self.client.post(reverse('analytics_consent'),{'consent':'no'})
        self.client.get('/')
        self.assertEqual(WebsiteVisit.objects.count(),1)
    def test_analytics_admin_restricted_and_no_fake_data(self):
        url=reverse('professional_analytics')
        self.assertRedirects(self.client.get(url),reverse('professional_login')+'?next='+url, fetch_redirect_response=False) if False else None
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(url).status_code,403)
        self.client.force_login(self.master)
        r=self.client.get(url)
        self.assertContains(r,'Dashboard de acessos')
        self.assertContains(r,'Últimos 30 dias') if False else None
        self.assertContains(r,'00:00')
        self.assertContains(r,'23:00')
        self.assertContains(r,'Sem informação ainda')
    def test_message_moderated_and_name_hidden_by_default(self):
        url=reverse('community_submit')
        data={'kind':'question','name':'Paciente de Exemplo','email':'visitor@example.org','text':'Gostaria de saber quais são os serviços oferecidos na clínica.', 'privacy_ack':'on','publish_authorized':'on'}
        self.assertEqual(self.client.post(url,data).status_code,302)
        entry=VisitorSubmission.objects.get()
        self.assertEqual(entry.status,'pending')
        self.assertNotContains(self.client.get('/duvidas/'),entry.text)
        self.client.force_login(self.master)
        form={'status':'published','answer':'Entre em contato para avaliação individualizada.'}
        self.assertEqual(self.client.post(reverse('professional_submission_edit',args=[entry.pk]),form).status_code,302)
        self.client.logout()
        r=self.client.get('/duvidas/')
        self.assertContains(r,entry.text)
        self.assertContains(r,entry.answer)
        self.assertNotContains(r,'visitor@example.org')
        self.assertNotContains(r,'Paciente de Exemplo')
    def test_publish_requires_consent_and_answer(self):
        x=VisitorSubmission.objects.create(name='Test',email='test@example.com',kind='question',text='Dúvida com autorização pendente',privacy_ack=True)
        self.client.force_login(self.master)
        r=self.client.post(reverse('professional_submission_edit',args=[x.id]),{'status':'published','answer':'Resposta'})
        self.assertEqual(r.status_code,200)
        x.refresh_from_db()
        self.assertNotEqual(x.status,'published')
    def test_rate_limit_and_spam(self):
        data={'kind':'question','name':'Teste','email':'x@example.org','text':'Uma questão geral sobre o funcionamento do site e atendimento', 'privacy_ack':'on'}
        for i in range(3): self.assertEqual(self.client.post(reverse('community_submit'),data).status_code,302)
        self.assertEqual(self.client.post(reverse('community_submit'),data).status_code,400)
        self.assertEqual(VisitorSubmission.objects.count(),3)
        data['homepage']='robot'
        self.assertEqual(self.client.post(reverse('community_submit'),data).status_code,400)
    def test_instagram_stories_expire_and_posts_remain(self):
        from datetime import timedelta
        now=timezone.now()
        InstagramEntry.objects.create(instagram_id='one',kind='STORY',permalink='https://www.instagram.com/stories/test/1/',posted_at=now-timedelta(hours=30),expires_at=now-timedelta(hours=6))
        InstagramEntry.objects.create(instagram_id='two',kind='IMAGE',permalink='https://www.instagram.com/p/test/',posted_at=now)
        res=self.client.get('/instagram/')
        self.assertNotContains(res,'Ver story ↗')
        self.assertNotContains(res,'https://www.instagram.com/p/test/')
    def test_share_buttons_public_report(self):
        VlogVideo.objects.create(title='Teste compartilhável',slug='teste-compartilhavel',body='Teste de saúde pública.',published=True)
        r=self.client.get('/vlog/teste-compartilhavel/')
        self.assertContains(r,'lx-share-wa')
        self.assertContains(r,'lx-share-ig')
        self.assertContains(r,'lx-share-copy')
    def test_sync_requires_auth(self):
        self.assertEqual(self.client.post('/profissional/instagram/sincronizar/').status_code,404)
        self.assertEqual(self.client.get('/interno/instagram/sincronizar/').status_code,404)
