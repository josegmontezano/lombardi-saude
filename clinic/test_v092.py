from django.test import TestCase

class ExactAlegreLocationTests(TestCase):
    def test_embedded_map_points_to_clinic_listing(self):
        res=self.client.get('/contato/')
        self.assertEqual(res.status_code, 200)
        self.assertContains(res,'q=Lombardi%20Sa%C3%BAde%20%7C%20Alegre%20ES')
        self.assertContains(res,'ll=-20.7634357%2C-41.5311083')
        self.assertNotContains(res,'maps?q=Spazio%20Center')
        self.assertContains(res,'Localização oficial da Lombardi Saúde — Alegre')
        self.assertContains(res,'https://www.google.com/maps?cid=16996666549391216811', count=2)

    def test_alegre_address_and_contacts_are_preserved(self):
        res=self.client.get('/contato/')
        for text in ('Spazio Center', 'Av. Jerônimo Monteiro, 113', 'Sala 10',
                     'Alegre/ES', 'CEP 29500-000', '(28) 99946-8688'):
            self.assertContains(res,text)

    def test_campo_grande_location_remains_correct(self):
        res=self.client.get('/contato/')
        self.assertContains(res,'ll=-22.9062702%2C-43.5596621')
        self.assertContains(res,'https://maps.app.goo.gl/12PyoDcwp8DkdkEBA',count=2)
        self.assertContains(res,'Salas 705 e 706')
