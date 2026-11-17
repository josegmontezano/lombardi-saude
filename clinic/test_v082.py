import base64, hashlib, hmac, json, time
from django.conf import settings
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from .models import VlogVideo

class ProtectedVlogTests(TestCase):
    def setUp(self):
        U=get_user_model()
        self.editor=U.objects.create_user(username='privateeditor', email='private.editor@example.com', password='testing123#S', role='staff', staff_job='doctor',is_staff=True)
        self.patient=U.objects.create_user(username='privatetestpatient',email='patient@example.com',password='testing123#S',role='patient')
        self.pathname=f'vlog/private/{self.editor.pk}/'+'a'*32+'.mp4'
    def test_private_video_publicly_watchable_without_login(self):
        VlogVideo.objects.create(title='Vídeo original',slug='video-original',body='',private_media_path=self.pathname,published=True)
        r=self.client.get('/vlog/video-original/')
        self.assertEqual(r.status_code,200)
        self.assertContains(r,'private-vlog-player')
        self.assertNotContains(r,self.pathname)
        self.assertContains(r,'data-playback-ticket=')
        self.assertEqual(r.headers.get('Cache-Control'),'no-store')
    def test_private_video_only_in_authored_path(self):
        self.client.force_login(self.editor)
        data={'title':'Novo vídeo privado','category':'prevencao','body':'','summary':'Teste','video_url':'','media_url':'','private_media_path':f'vlog/private/999999/'+ 'f'*32+'.mp4','cover_url':'','published':'on'}
        r=self.client.post(reverse('professional_post_new'),data)
        self.assertEqual(r.status_code,200)
        self.assertFalse(VlogVideo.objects.filter(title='Novo vídeo privado').exists())
    def test_patient_cannot_publish(self):
        self.client.force_login(self.patient)
        self.assertEqual(self.client.get(reverse('professional_post_new')).status_code,403)
    def test_unpublished_video_is_not_watchable(self):
        VlogVideo.objects.create(title='Rascunho privado',slug='rascunho-privado',private_media_path=self.pathname,published=False)
        self.assertEqual(self.client.get('/vlog/rascunho-privado/').status_code,404)

    def test_editor_can_publish_owned_private_path(self):
        self.client.force_login(self.editor)
        r=self.client.post(reverse('professional_post_new'),{'title':'Novo vídeo','category':'prevencao','body':'','summary':'Descrição','video_url':'','media_url':'','private_media_path':self.pathname,'cover_url':'','published':'on'})
        self.assertEqual(r.status_code,302)
        self.assertTrue(VlogVideo.objects.filter(title='Novo vídeo',published=True,private_media_path=self.pathname).exists())
