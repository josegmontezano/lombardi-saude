from django.db import migrations,models

class Migration(migrations.Migration):
    dependencies = [('clinic','0011_vlogvideo')]
    operations = [
        migrations.AlterField(model_name='vlogvideo',name='summary',field=models.TextField('Resumo para a lista de publicações',blank=True)),
        migrations.AlterField(model_name='vlogvideo',name='video_url',field=models.URLField('Link externo de vídeo (opcional)',max_length=500,blank=True)),
        migrations.AddField(model_name='vlogvideo',name='body',field=models.TextField('Texto da reportagem / artigo (sem limite editorial)',blank=True)),
        migrations.AddField(model_name='vlogvideo',name='cover_url',field=models.URLField('URL da capa no armazenamento Vercel',max_length=900,blank=True)),
        migrations.AddField(model_name='vlogvideo',name='media_url',field=models.URLField('URL de vídeo armazenado na Vercel',max_length=900,blank=True)),
    ]
