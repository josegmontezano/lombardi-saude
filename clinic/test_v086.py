from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import InstagramEntry
User=get_user_model()
class InstagramOnlyManualEmbedTests(TestCase):
    def setUp(self):
        self.admin=User.objects.create_superuser('test086','test086@example.com','Strong-password!086')
        self.post='https://www.instagram.com/p/ABCdefgh1aB/'
        self.reel='https://www.instagram.com/reel/CBAfedgh2bC/'
    def test_posts_only_public_no_stories_and_no_account_api(self):
        InstagramEntry.objects.create(instagram_id='manual:p:ABCdefgh1aB',kind='IMAGE',permalink=self.post,posted_at=timezone.now())
        InstagramEntry.objects.create(instagram_id='sync-story',kind='STORY',permalink='https://www.instagram.com/stories/example/1/',posted_at=timezone.now())
        res=self.client.get(reverse('instagram_feed'))
        self.assertContains(res,self.post)
        self.assertContains(res,'instagram-media')
        self.assertContains(res,'https://www.instagram.com/embed.js')
        self.assertNotContains(res,'Stories recentes')
        self.assertNotContains(res,'sync-story')
        self.assertNotContains(res,'Conexão pendente')
    def test_professional_only_can_add_urls(self):
        url=reverse('professional_instagram')
        self.assertEqual(self.client.post(url,{'url':self.post}).status_code,302)
        self.assertFalse(InstagramEntry.objects.exists())
        self.client.force_login(self.admin)
        r=self.client.post(url,{'url':self.post+'?utm_source=chatgpt'},follow=True)
        self.assertEqual(r.status_code,200)
        item=InstagramEntry.objects.get(instagram_id__startswith='manual:')
        self.assertEqual(item.permalink,self.post)
        self.assertContains(self.client.get(reverse('instagram_feed')),self.post)
    def test_invalid_urls_rejected(self):
        self.client.force_login(self.admin)
        for url in ('https://evil.example.com/p/ABCdefgh1aB/','https://instagram.com.evil.com/p/ABCdefgh1aB/','http://www.instagram.com/p/ABCdefgh1aB/','https://www.instagram.com/stories/lombardi.saude/12345/','https://www.instagram.com/lombardi.saude/'):
            resp=self.client.post(reverse('professional_instagram'),{'url':url})
            self.assertEqual(resp.status_code,200)
        self.assertFalse(InstagramEntry.objects.exists())
    def test_delete_post_restricted(self):
        item=InstagramEntry.objects.create(instagram_id='manual:p:ABCdefgh1aB',kind='IMAGE',permalink=self.post,posted_at=timezone.now())
        url=reverse('professional_instagram_remove',kwargs={'pk':item.pk})
        self.client.post(url)
        self.assertTrue(InstagramEntry.objects.filter(pk=item.pk).exists())
        self.client.force_login(self.admin)
        self.assertRedirects(self.client.post(url),reverse('professional_instagram'))
        self.assertFalse(InstagramEntry.objects.filter(pk=item.pk).exists())
    def test_no_auto_sync_endpoints(self):
        self.assertEqual(self.client.get('/interno/instagram/sincronizar/').status_code,404)
        self.assertEqual(self.client.post('/profissional/instagram/sincronizar/').status_code,404)
