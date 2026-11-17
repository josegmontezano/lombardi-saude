from pathlib import Path
from django.test import TestCase
from django.urls import reverse
from django.contrib.staticfiles import finders

class HighResolutionPhotoTests(TestCase):
    def test_home_displays_high_quality_assets_and_responsive_sources(self):
        res=self.client.get(reverse('home'))
        self.assertContains(res,'hero-hq.webp')
        self.assertContains(res,'hero-800.webp')
        self.assertContains(res,'about-hq.webp')
        self.assertNotContains(res,'img/booking.webp')
        self.assertContains(res,'card-clinica-hq.webp')
        self.assertContains(res,'v0.8.9')
        self.assertNotContains(res,'img/hero.webp')

    def test_vlog_portrait_from_original_ensaios(self):
        res=self.client.get(reverse('vlog_index'))
        self.assertContains(res,'vlog-portrait-hq.webp')
        self.assertContains(res,'vlog-portrait-800.webp')

    def test_every_high_quality_image_exists_and_is_not_tiny(self):
        files=['hero-hq.webp','about-hq.webp','booking-hq.webp',
               'vlog-portrait-hq.webp','card-clinica-hq.webp','card-prevencao-hq.webp',
               'card-peso-hq.webp','card-corpo-hq.webp','card-terapia-hq.webp','card-mulher-hq.webp']
        for name in files:
            with self.subTest(name=name):
                p=finders.find('img/'+name)
                self.assertIsNotNone(p)
                self.assertGreater(Path(p).stat().st_size,40000)
