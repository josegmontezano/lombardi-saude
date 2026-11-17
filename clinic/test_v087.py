from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import InstagramEntry

class InstagramProfileEmbedTests(TestCase):
    def test_public_gallery_without_profile_panel_or_login(self):
        response=self.client.get('/instagram/')
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'Publicações <em>@lombardi.saude</em>')
        self.assertNotContains(response,'data-instgrm-permalink="https://www.instagram.com/lombardi.saude/"')
        self.assertNotContains(response,'lx-ig-official-profile')
        self.assertContains(response,'https://www.instagram.com/embed.js')
        self.assertNotContains(response,'Visualizar perfil no Instagram')
        self.assertNotContains(response,'Conexão pendente')
        self.assertNotContains(response,'Stories recentes')
        self.assertNotContains(response,'Sincronizar agora')

    def test_embedded_public_profile_and_manually_selected_post_together(self):
        InstagramEntry.objects.create(
            instagram_id='manual:p:ABC987abc12',kind='IMAGE',
            permalink='https://www.instagram.com/p/ABC987abc12/',
            posted_at=timezone.now(),
        )
        res=self.client.get('/instagram/')
        self.assertNotContains(res,'data-instgrm-permalink="https://www.instagram.com/lombardi.saude/"')
        self.assertContains(res,'data-instgrm-permalink="https://www.instagram.com/p/ABC987abc12/"')
        self.assertContains(res,'Publicações do Instagram')

    def test_no_portal_account_required(self):
        self.assertEqual(self.client.get('/instagram/').status_code,200)
        self.assertNotContains(self.client.get('/instagram/'),'Entrar para visualizar')
