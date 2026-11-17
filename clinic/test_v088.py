from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.urls import reverse
from .models import InstagramEntry

class InstagramTwentyPostsTests(TestCase):
    def setUp(self):
        self.admin=get_user_model().objects.create_superuser(
            'instagrambulk88','bulk88@example.com','secure-test-88!')
        self.url=reverse('professional_instagram')

    def test_exactly_twenty_posts_appear_on_first_page(self):
        for i in range(20):
            code=f'PostID{i:05d}'
            InstagramEntry.objects.create(instagram_id=f'manual:p:{code}',
                permalink=f'https://www.instagram.com/p/{code}/',
                kind='IMAGE',posted_at=timezone.now())
        resp=self.client.get('/instagram/')
        self.assertEqual(resp.status_code,200)
        self.assertEqual(len(resp.context['posts']),20)
        self.assertContains(resp,'20 espaços visíveis por página')
        self.assertContains(resp,'PostID00019')
        self.assertContains(resp,'PostID00000')

    def test_pagination_shows_20_then_remaining_without_duplicates(self):
        for i in range(41):
            code=f'PostID{i:05d}'
            InstagramEntry.objects.create(instagram_id=f'manual:p:{code}',
                permalink=f'https://www.instagram.com/p/{code}/',
                kind='IMAGE',posted_at=timezone.now())
        first=self.client.get('/instagram/')
        second=self.client.get('/instagram/?pagina=2')
        third=self.client.get('/instagram/?pagina=3')
        self.assertEqual([len(r.context['posts']) for r in (first,second,third)],[20,20,1])
        self.assertContains(first,'Ver mais 20 publicações')
        self.assertNotContains(first,'PostID00000')
        self.assertContains(third,'PostID00000')

    def test_bulk_twenty_real_shape_links_only_authorized(self):
        raw='\n'.join(f'https://www.instagram.com/p/Clinic{i:05d}/' for i in range(20))
        anon=self.client.post(self.url,{'operation':'bulk','links':raw})
        self.assertEqual(anon.status_code,302)
        self.assertEqual(InstagramEntry.objects.count(),0)
        self.client.force_login(self.admin)
        res=self.client.post(self.url,{'operation':'bulk','links':raw})
        self.assertRedirects(res,self.url)
        self.assertEqual(InstagramEntry.objects.count(),20)
        # Repeat the same batch: never duplicate posts.
        self.client.post(self.url,{'operation':'bulk','links':raw})
        self.assertEqual(InstagramEntry.objects.count(),20)
        self.assertEqual(len(self.client.get('/instagram/').context['posts']),20)

    def test_bulk_rejects_invalid_links_atomically(self):
        self.client.force_login(self.admin)
        bad='https://www.instagram.com/p/ValidClinic01/\nhttps://evil.example/p/InvalidClinic1/'
        res=self.client.post(self.url,{'operation':'bulk','links':bad})
        self.assertEqual(res.status_code,200)
        self.assertEqual(InstagramEntry.objects.count(),0)
        self.assertContains(res,'Links inválidos nas linhas')

    def test_stories_are_hidden_and_no_auto_sync_required(self):
        InstagramEntry.objects.create(instagram_id='manual:p:ValidClinic11',
            permalink='https://www.instagram.com/p/ValidClinic11/',
            kind='IMAGE',posted_at=timezone.now())
        InstagramEntry.objects.create(instagram_id='manual:story:ABC0123',
            permalink='https://www.instagram.com/stories/lombardi.saude/123/',
            kind='STORY',posted_at=timezone.now())
        res=self.client.get('/instagram/')
        self.assertContains(res,'ValidClinic11')
        self.assertNotContains(res,'ABC0123')


    def test_empty_gallery_renders_twenty_real_visible_reserve_slots(self):
        res=self.client.get('/instagram/')
        self.assertEqual(res.status_code,200)
        self.assertEqual(res.content.count(b'class="lx-ig-manual-post lx-ig-slot"'),20)
        self.assertContains(res,'PUBLICAÇÃO 01')
        self.assertContains(res,'PUBLICAÇÃO 20')
        self.assertNotContains(res,'https://www.instagram.com/p/FAKE')

    def test_real_posts_replace_placeholders_not_add_extra(self):
        code='OfficialClinic001'
        InstagramEntry.objects.create(instagram_id='manual:p:'+code,
            permalink='https://www.instagram.com/p/'+code+'/',
            kind='IMAGE',posted_at=timezone.now())
        res=self.client.get('/instagram/')
        self.assertEqual(res.content.count(b'class="lx-ig-manual-post lx-ig-slot"'),19)
        self.assertContains(res,code)
        self.assertContains(res,'PUBLICAÇÃO 20')
