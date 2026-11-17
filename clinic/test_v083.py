from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from .models import VlogVideo
from .templatetags.vlog_format import vlog_article

class VlogEditorialLayoutTests(TestCase):
    def test_report_article_branding_breadcrumb_appointments_and_text(self):
        v=VlogVideo.objects.create(title='Bem-estar e cuidado',slug='bem-estar-cuidado',category='prevencao',summary='Entenda a importância da prevenção.',body='## O que é prevenção?\n\nCuidados individualizados.\n\n- Sono\n- Alimentação',published=True)
        r=self.client.get(reverse('vlog_detail',kwargs={'slug':v.slug}))
        self.assertEqual(r.status_code,200)
        self.assertContains(r,'Tirando Dúvidas com a Lombardi Saúde')
        self.assertContains(r,'Dra. Isabella Lombardi')
        self.assertContains(r,'O que é prevenção?')
        self.assertContains(r,'<h2>O que é prevenção?</h2>',html=False)
        self.assertContains(r,'<li>Sono</li>',html=False)
        self.assertContains(r,'5521986825542')
        self.assertContains(r,'5528999468688')
        self.assertContains(r,'Agende sua consulta')
        self.assertNotContains(r,'<script defer src="/static/js/private-vlog-player.js?v=082"></script>')
    def test_unpublished_not_accessible(self):
        v=VlogVideo.objects.create(title='Privado',slug='nao-publicado-083',body='não publicado',published=False)
        self.assertEqual(self.client.get(reverse('vlog_detail',kwargs={'slug':v.slug})).status_code,404)
    def test_safely_escapes_html_in_article(self):
        text=vlog_article('## <script>malicioso</script>\n\n<script>alert(9)</script>\n\n- <b>item</b>')
        self.assertNotIn('<script>',text)
        self.assertNotIn('<b>item</b>',text)
        self.assertIn('&lt;script&gt;',text)
        self.assertIn('<h2>',text)
        self.assertIn('<li>',text)
    def test_pages_available_and_portals_unchanged(self):
        for url in ['/','/vlog/','/contato/','/profissional/entrar/']:
            self.assertEqual(self.client.get(url).status_code,200)
        self.assertEqual(self.client.get('/paciente/login/').status_code,410)
