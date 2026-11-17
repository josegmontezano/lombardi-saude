from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User=get_user_model()

class MasterAccessTests(TestCase):
    def setUp(self):
        User.objects.create_superuser(
            username="test-master@example.test",
            email="test-master@example.test",
            password="StrongTestPassword!2026",
            role=User.ADMIN, must_change_password=True,
        )

    def test_master_is_provisioned_interactively(self):
        boss=User.objects.get(email="test-master@example.test")
        self.assertEqual(boss.username,"test-master@example.test")
        self.assertEqual(boss.role,User.ADMIN)
        self.assertTrue(boss.is_active and boss.is_staff and boss.is_superuser)
        self.assertTrue(boss.must_change_password)
        self.assertTrue(boss.has_usable_password())

    def test_master_first_login_requires_password_change(self):
        boss=User.objects.get(email="test-master@example.test")
        self.client.force_login(boss)
        r=self.client.get(reverse("master_access"))
        self.assertRedirects(r,reverse("professional_password_change"),fetch_redirect_response=False)
        r=self.client.get(reverse("professional_password_change"))
        self.assertEqual(r.status_code,200)
        self.assertContains(r,"senha",status_code=200)
        self.assertTrue(self.client.post(reverse("professional_password_change"),{}).status_code in (200,400))

    def test_master_after_password_change_sees_master_page(self):
        boss=User.objects.get(email="test-master@example.test")
        boss.must_change_password=False
        boss.save(update_fields=["must_change_password"])
        self.client.force_login(boss)
        self.assertEqual(self.client.get(reverse("master_access")).status_code,200)
        self.assertContains(self.client.get(reverse("master_access")),"Acesso mestre")
        self.assertEqual(self.client.get(reverse("management_access")).status_code,200)

    def test_other_users_cannot_access_master(self):
        user=User.objects.create_user(username="regular",email="regular@example.test",password="ValidPass!2026",role=User.ADMIN,is_active=True)
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse("master_access")).status_code,200)
        self.client.logout()
        self.assertEqual(self.client.get(reverse("master_access")).status_code,302)

