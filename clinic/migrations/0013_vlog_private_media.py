from django.db import migrations, models
class Migration(migrations.Migration):
    dependencies=[('clinic','0012_vlog_article_media')]
    operations=[migrations.AddField(model_name='vlogvideo',name='private_media_path',field=models.CharField(blank=True,default='',max_length=280,verbose_name='Caminho privado do vídeo'))]
