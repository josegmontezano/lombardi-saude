from django.test import TestCase
from django.urls import reverse, resolve
from django.utils import timezone
from datetime import timedelta
from django.core.exceptions import ValidationError
from .models import VlogVideo

class InstitutionalVlogTests(TestCase):
    def test_public_site_has_no_portal_ctas(self):
        for url in ['/', '/contato/', '/sobre/', '/especialidades/', '/servicos/', '/tecnologia/']:
            res = self.client.get(url)
            self.assertEqual(res.status_code, 200)
            self.assertNotContains(res, 'Área do Paciente')
            self.assertNotContains(res, 'Área Profissional')
            self.assertNotContains(res, 'Portal do Paciente')
            self.assertNotContains(res, 'Para Pacientes')
            self.assertNotContains(res, 'Para Profissionais')
    def test_legacy_private_urls_are_disabled(self):
        for path in ['/paciente/', '/paciente/login/', '/paciente/cadastro/', '/paciente/notas/', '/funcionario/', '/funcionario/login/', '/notificacoes/']:
            self.assertEqual(self.client.get(path).status_code, 410, path)
    def test_vlog_empty_page(self):
        res=self.client.get('/vlog/')
        self.assertEqual(res.status_code,200)
        self.assertContains(res,'Em breve, novos vídeos')
    def test_published_video_and_detail(self):
        v=VlogVideo.objects.create(title='Saúde e prevenção',slug='saude-e-prevencao',category='prevencao',summary='Conteúdo educativo.',video_url='https://youtu.be/dQw4w9WgXcQ',published=True)
        self.assertContains(self.client.get('/vlog/'), v.title)
        self.assertContains(self.client.get('/vlog/saude-e-prevencao/'),'youtube-nocookie.com/embed/dQw4w9WgXcQ')
    def test_unpublished_and_scheduled_are_not_visible(self):
        VlogVideo.objects.create(title='Privado',slug='privado',summary='texto',video_url='https://youtu.be/dQw4w9WgXcQ',published=False)
        VlogVideo.objects.create(title='Futuro',slug='futuro',summary='texto',video_url='https://youtu.be/dQw4w9WgXcQ',published=True,publish_at=timezone.now()+timedelta(days=3))
        self.assertNotContains(self.client.get('/vlog/'),'Privado')
        self.assertNotContains(self.client.get('/vlog/'),'Futuro')
        self.assertEqual(self.client.get('/vlog/privado/').status_code,404)
        self.assertEqual(self.client.get('/vlog/futuro/').status_code,404)
    def test_categories_are_filterable(self):
        VlogVideo.objects.create(title='Alimentação saudável',slug='alimentacao',summary='texto',video_url='https://youtu.be/dQw4w9WgXcQ',category='nutricao',published=True)
        VlogVideo.objects.create(title='Outra matéria',slug='outra',summary='texto',video_url='https://youtu.be/dQw4w9WgXcQ',category='duvidas',published=True)
        r=self.client.get('/vlog/?categoria=nutricao')
        self.assertContains(r,'Alimentação saudável')
        self.assertNotContains(r,'Outra matéria')
    def test_rejects_external_and_insecure_video_links(self):
        for url in ['http://youtu.be/dQw4w9WgXcQ','https://example.com/embed/dQw4w9WgXcQ','https://youtube.com.evil.com/watch?v=dQw4w9WgXcQ']:
            with self.assertRaises(ValidationError):
                VlogVideo.objects.create(title='Inseguro',slug='inseguro',summary='texto',video_url=url,published=True)
    def test_instagram_is_external_only(self):
        v=VlogVideo.objects.create(title='Reel',slug='reel',summary='texto',video_url='https://www.instagram.com/reel/ABCdef01234/',published=True)
        self.assertFalse(v.embed_url)
        self.assertContains(self.client.get('/vlog/reel/'),'Abrir vídeo no Instagram')
    def test_contact_has_separate_phones(self):
        r=self.client.get('/contato/')
        self.assertContains(r,'(21) 98682-5542')
        self.assertContains(r,'(28) 99946-8688')
