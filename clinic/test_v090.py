from django.test import TestCase

class CampoGrandeMapTests(TestCase):
    def test_campo_grande_address_matches_official_information(self):
        res=self.client.get('/contato/')
        self.assertEqual(res.status_code,200)
        for text in ('Av. Cesário de Melo, 2855', 'Salas 705 e 706', 'Campo Grande', 'Rio de Janeiro/RJ', 'CEP 23052-101'):
            self.assertContains(res,text)

    def test_two_map_actions_use_provided_direct_google_maps_link(self):
        res=self.client.get('/contato/')
        self.assertContains(res,'https://maps.app.goo.gl/12PyoDcwp8DkdkEBA',count=2)
        self.assertNotContains(res,'maps/search/?api=1&amp;query=Avenida%20Ces')

    def test_embedded_maps_and_alegre_are_preserved(self):
        res=self.client.get('/contato/')
        self.assertContains(res,'Mapa da Lombardi Saúde — Campo Grande')
        self.assertContains(res,'Mapa da Lombardi Saúde — Alegre')
        self.assertContains(res,'Spazio Center')
        self.assertContains(res,'(28) 99946-8688')
        self.assertContains(res,'(21) 98682-5542')


class ExactLombardiClinicMapTests(TestCase):
    def test_iframe_uses_clinic_place_and_exact_location(self):
        res=self.client.get('/contato/')
        self.assertContains(res,'ll=-22.9062702%2C-43.5596621')
        self.assertContains(res,'q=Lombardi%20Sa%C3%BAde%20%7C%20Dra%20Isabella%20Lombardi%20-%20Nutrologia')
        self.assertNotContains(res,'maps?q=Avenida%20Ces%C3%A1rio%20de%20Melo')
        self.assertContains(res,'Localização da Lombardi Saúde no número 2855')
        self.assertContains(res,'https://maps.app.goo.gl/12PyoDcwp8DkdkEBA',count=2)
        self.assertContains(res,'Mapa da Lombardi Saúde — Alegre')
