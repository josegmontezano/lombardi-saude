from django.db import migrations

# Descrições informativas; não se confundem com prescrições ou especificações farmacotécnicas.
ITEMS = [
 ('Morosil','nutraceutico','Extrato de laranja Moro estudado para composição corporal; efeitos clínicos são incertos e não substitui tratamento alimentar e médico.'),
 ('Mounjaro 2,5 MG','medicamento','Tirzepatida (Eli Lilly), agonista GIP/GLP-1, utilizada conforme indicação aprovada e prescrição. Apresentação de 2,5 mg; avaliação médica obrigatória.'),
 ('Mounjaro 5 MG','medicamento','Tirzepatida (Eli Lilly), tratamento prescrito para diabetes tipo 2 e controle crônico do peso em condições específicas. Apresentação de 5 mg.'),
 ('Mounjaro 7,5 MG','medicamento','Tirzepatida (Eli Lilly), apresentação de 7,5 mg para tratamento sob acompanhamento e avaliação de segurança e tolerabilidade.'),
 ('Protocolo LipoImpulse','formula','Nome de protocolo de finalidade metabólica/estética informada pela clínica. Composição, indicação e comprovação de resultados precisam de ficha técnica.'),
 ('Vitamina ADEK','nutriente','Associação de vitaminas lipossolúveis A, D, E e K. Excesso pode causar toxicidade; suplementação somente se indicada.'),
 ('Complexo B completo','nutriente','Associação de vitaminas do grupo B envolvidas no metabolismo e no sistema nervoso. Composição e necessidade variam por fórmula.'),
 ('Ferro','nutriente','Mineral essencial à hemoglobina e ao transporte de oxigênio. Reposição depende de avaliação de deficiência e risco de sobrecarga.'),
 ('Complexo B','nutriente','Combinação de vitaminas B em proporções específicas. Avaliar formulação e necessidade individual.'),
 ('Metilfolato','nutriente','Forma de folato (vitamina B9), importante na síntese celular e na produção de células sanguíneas; não dispensa investigação da deficiência.'),
 ('Vitamina B12','nutriente','Nutriente essencial à formação de células sanguíneas e ao funcionamento neurológico. Usado conforme deficiência ou condição clínica.'),
 ('Vitamina D3','nutriente','Vitamina relacionada à regulação do cálcio e à saúde óssea. Suplementação conforme avaliação de necessidade.'),
 ('Vitamina E','nutriente','Vitamina lipossolúvel com função antioxidante. Doses excessivas podem trazer riscos.'),
 ('Vitamina C','nutriente','Nutriente envolvido na formação do colágeno e nas defesas antioxidantes; indicação depende da necessidade nutricional.'),
 ('Antioxidante','formula','Associação de compostos para suporte antioxidante. Os ingredientes e as evidências precisam ser conferidos na formulação.'),
 ('Cabelos e unhas','formula','Combinação nutricional proposta para saúde capilar e ungueal. Benefício depende de fatores e deficiências identificados.'),
 ('BCAA’S','nutraceutico','Aminoácidos de cadeia ramificada (leucina, isoleucina e valina); evidência adicional sobre dieta adequada é variável.'),
 ('Emagrecer/ ganho de massa','cuidado','Acompanhamento individualizado para composição corporal, alimentação e treinamento; não é uma fórmula de eficácia garantida.'),
 ('Lipedema','cuidado','Cuidado multidisciplinar para lipedema, incluindo avaliação, orientação e medidas conservadoras conforme indicação profissional.'),
 ('Ácido Alfa Lipóico','nutraceutico','Composto envolvido no metabolismo energético e estudado em situações de estresse oxidativo e neuropatia; evidência depende da indicação.'),
 ('BCAA + HIDROXIMETILBUTIRATO','formula','Associação de aminoácidos ramificados com HMB, estudada para manutenção muscular em contextos específicos; eficácia variável.'),
 ('Coenzima Q-10','nutraceutico','Composto presente na cadeia de produção de energia mitocondrial; possíveis usos dependem do quadro clínico.'),
 ('Cúrcuma','nutraceutico','Preparações com curcuminoides, estudadas em processos inflamatórios; formulação e evidência clínica são variáveis.'),
 ('Imune plus','formula','Nome de associação destinada a suporte nutricional/imunológico. A composição exata exige conferência no catálogo da farmácia.'),
 ('Pool de aminoácidos','formula','Mistura de aminoácidos cuja finalidade e adequação dependem dos componentes, da avaliação nutricional e da prescrição.'),
 ('Resveratrol','nutraceutico','Polifenol estudado por propriedades antioxidantes; benefícios clínicos específicos ainda são incertos.'),
 ('Zinco','nutriente','Mineral importante para imunidade, cicatrização e processos enzimáticos; excesso pode causar deficiência de cobre.'),
 ('Pill food','formula','Nome usado para combinações de nutrientes de suporte capilar; formulação e eficácia devem ser verificadas.'),
 ('L carnetina','nutraceutico','L-carnitina participa do transporte de ácidos graxos para produção de energia; não garante perda de peso.'),
]


def seed(apps, schema_editor):
    Protocol = apps.get_model('clinic','Protocol')
    for order,(name,category,description) in enumerate(ITEMS,1):
        supplier = ('Eli Lilly do Brasil — Mounjaro®; não é produto de marca StinPharma.'
                    if name.startswith('Mounjaro') else
                    'StinPharma — referência informada pela clínica; formulação a confirmar.')
        Protocol.objects.update_or_create(name=name,defaults={
            'category':category,'description':description,'supplier_reference':supplier,
            'prescription_required':True,'medically_reviewed':False,'active':True,'sort_order':order
        })


def unseed(apps, schema_editor):
    Protocol=apps.get_model('clinic','Protocol')
    Protocol.objects.filter(name__in=[x[0] for x in ITEMS], medically_reviewed=False).delete()

class Migration(migrations.Migration):
    dependencies=[('clinic','0004_patientprofile_protocol')]
    operations=[migrations.RunPython(seed,unseed)]
