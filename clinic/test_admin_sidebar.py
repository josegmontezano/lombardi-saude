from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from .models import VlogVideo, InstagramEntry
from .publication_forms import VlogPostForm

User = get_user_model()

class AdminSidebarAndPublishingTests(TestCase):
    def setUp(self):
        self.manager=User.objects.create_user(
            username="test-admin-nav",email="test-admin-nav@example.test",
            password="testing-secret-admin-42!",role=User.ADMIN,is_active=True,is_staff=True
        )

    def test_private_pages_display_sidebar_only_when_authenticated(self):
        self.assertNotContains(self.client.get(reverse("home")),"Menu lateral administrativo")
        self.client.force_login(self.manager)
        for name in ("management_access","professional_posts","professional_post_new","professional_analytics","review_dashboard"):
            response=self.client.get(reverse(name))
            self.assertEqual(response.status_code,200,name)
            self.assertContains(response,'class="lx-admin-shell"')
            self.assertContains(response,"Menu lateral administrativo")
            self.assertContains(response,"Menu administrativo móvel")
            self.assertContains(response,"Tirando Dúvidas")
        response=self.client.get(reverse("home"))
        self.assertNotContains(response,"Menu lateral administrativo")

    def test_nonpublisher_staff_not_shown_private_content_links(self):
        other=User.objects.create_user(
            username="test-frontdesk-nav",email="test-frontdesk-nav@example.test",
            password="testing-secret-42!",role=User.STAFF,staff_job=User.JOB_RECEPTION,
            is_active=True,is_staff=False
        )
        self.client.force_login(other)
        response=self.client.get(reverse("professional_access_home"))
        self.assertContains(response,"Menu administrativo móvel")
        self.assertNotContains(response,'href="'+reverse("professional_post_new")+'"')
        self.assertNotContains(response,'href="'+reverse("management_access")+'"')

    def test_publishing_default_and_public_vlog(self):
        self.assertTrue(VlogVideo._meta.get_field("published").default)
        self.assertTrue(VlogPostForm().fields["published"].initial is None or
                        VlogPostForm().instance.published)
        self.client.force_login(self.manager)
        resp=self.client.get(reverse("professional_post_new"))
        self.assertEqual(resp.status_code,200)
        self.assertContains(resp,"marcado por padrão")
        response=self.client.post(reverse("professional_post_new"),{
            "title":"Como cuidar da saúde e qualidade de vida",
            "category":"prevencao",
            "summary":"Orientações de saúde.",
            "body":"Informações para entender prevenção, sem dados pessoais.",
            "published":"on",
        })
        self.assertEqual(response.status_code,302)
        post=VlogVideo.objects.get(title="Como cuidar da saúde e qualidade de vida")
        self.assertTrue(post.published)
        self.assertLessEqual(post.publish_at,timezone.now())
        self.assertContains(self.client.get(reverse("vlog_index")),post.title)
        self.assertContains(self.client.get(reverse("vlog_detail",args=[post.slug])),post.summary)
        self.assertContains(self.client.get(reverse("professional_posts")),"No Tirando Dúvidas")

    def test_drafts_are_private_and_scheduled_items_wait(self):
        draft=VlogVideo.objects.create(title="Rascunho editorial privado",slug="rascunho-privado",body="Em edição",published=False)
        future=VlogVideo.objects.create(title="Publicação programada",slug="post-futuro",body="Ainda não publicada",published=True,publish_at=timezone.now()+timedelta(days=3))
        public=self.client.get(reverse("vlog_index"))
        self.assertNotContains(public,draft.title)
        self.assertNotContains(public,future.title)
        self.assertEqual(self.client.get(reverse("vlog_detail",args=[draft.slug])).status_code,404)
        self.assertEqual(self.client.get(reverse("vlog_detail",args=[future.slug])).status_code,404)

    def test_instagram_posts_in_tirando_duvidas(self):
        now=timezone.now()
        InstagramEntry.objects.create(
            instagram_id="ig-test-223", kind="IMAGE", caption="Saúde e bem-estar",
            permalink="https://www.instagram.com/p/ABCDE1/",posted_at=now
        )
        r=self.client.get(reverse("vlog_index"))
        self.assertNotContains(r,"Publicações do Instagram")
        self.assertNotContains(r,"https://www.instagram.com/p/ABCDE1/")

    def test_master_can_navigate_editorial_from_sidebar(self):
        master=User.objects.create_superuser(username="test-super-nav",email="test-super-nav@example.test",password="testing-super-secret!")
        master.must_change_password=False
        master.save(update_fields=["must_change_password"])
        self.client.force_login(master)
        response=self.client.get(reverse("master_access"))
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'href="'+reverse("professional_posts")+'"')
        self.assertContains(response,"Menu lateral administrativo")
        self.assertContains(response,"Criar publicação")
