from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import VlogVideo

class EditorialPortalTests(TestCase):
    def setUp(self):
        U=get_user_model()
        self.editor=U.objects.create_user(username='editor081',email='editor081@example.org',password='TestOnly!345',role='staff',staff_job='doctor',is_staff=True)
        self.viewer=U.objects.create_user(username='viewer081',email='viewer081@example.org',password='TestOnly!345',role='patient')
    def test_technology_removed_and_unpublished_private(self):
        self.assertEqual(self.client.get('/tecnologia/').status_code,410)
        self.assertNotContains(self.client.get('/'),'Tecnologia</a>')
        self.assertNotContains(self.client.get('/vlog/'),'profissional/publicacoes/')
    def test_public_vlog_no_auth_required(self):
        post=VlogVideo.objects.create(title='Texto sobre hábitos',slug='texto-habitos',body='Texto informativo longo',published=True)
        r=self.client.get('/vlog/texto-habitos/')
        self.assertContains(r,'Texto informativo longo')
        self.assertContains(r,'wa.me/5521986825542')
        self.assertContains(r,'wa.me/5528999468688')
    def test_editor_permission(self):
        self.assertEqual(self.client.get('/profissional/publicacoes/').status_code,302)
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get('/profissional/publicacoes/').status_code,403)
        self.client.force_login(self.editor)
        self.assertEqual(self.client.get('/profissional/publicacoes/').status_code,200)
    def test_publish_article(self):
        self.client.force_login(self.editor)
        d={'title':'Novo artigo da Dra. Isabella','category':'prevencao','body':'Informação clínica educativa, sem dados pessoais.','summary':'Uma orientação','video_url':'','media_url':'','cover_url':'','published':'on'}
        r=self.client.post('/profissional/publicacoes/nova/',d)
        self.assertEqual(r.status_code,302)
        p=VlogVideo.objects.get(title=d['title'])
        self.assertTrue(p.published)
        self.assertContains(self.client.get('/vlog/'),p.title)
    def test_unpublished_hidden(self):
        VlogVideo.objects.create(title='Rascunho',slug='rascunho',body='Texto interno')
        self.assertEqual(self.client.get('/vlog/rascunho/').status_code,404)
    def test_external_media_domain_rejected(self):
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            VlogVideo.objects.create(title='Ataque',slug='ataque',body='Textinho',media_url='https://evil.example.com/vlog/b.mp4')
    def test_only_post_to_logout(self):
        self.client.force_login(self.editor)
        self.assertEqual(self.client.get('/profissional/sair/').status_code,302)
        self.assertTrue(self.client.session.session_key)
        self.assertEqual(self.client.post('/profissional/sair/').status_code,302)
        self.assertNotIn('_auth_user_id',self.client.session)
