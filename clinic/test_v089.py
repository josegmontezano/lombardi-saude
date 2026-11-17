from django.test import TestCase

class InstagramWithoutProfileTests(TestCase):
    def test_only_publications_remain(self):
        response = self.client.get('/instagram/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Publicações do Instagram')
        self.assertNotContains(response, 'lx-ig-profile-frame')
        self.assertNotContains(response, 'lx-ig-official-profile')
        self.assertNotContains(response, 'PERFIL PÚBLICO')
        self.assertNotContains(response, 'data-instgrm-permalink="https://www.instagram.com/lombardi.saude/"')
        self.assertEqual(response.content.count(b'class="lx-ig-manual-post lx-ig-slot"'), 20)
