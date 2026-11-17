from django.db import migrations, models
import django.utils.timezone

class Migration(migrations.Migration):
    dependencies = [('clinic', '0010_patient_registration_fiscal_snapshot')]
    operations = [migrations.CreateModel(name='VlogVideo', fields=[
        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
        ('title', models.CharField(max_length=180, verbose_name='Título do vídeo')),
        ('slug', models.SlugField(max_length=180, unique=True, verbose_name='Endereço da publicação')),
        ('category', models.CharField(choices=[('prevencao','Prevenção e saúde'), ('metabolismo','Metabolismo e peso'), ('nutricao','Nutrição e hábitos'), ('bem-estar','Qualidade de vida'), ('duvidas','Dúvidas frequentes'), ('institucional','Institucional')], default='prevencao', max_length=30, verbose_name='Categoria')),
        ('summary', models.TextField(max_length=1800, verbose_name='Descrição')),
        ('video_url', models.URLField(max_length=500, verbose_name='Link do vídeo (YouTube, Vimeo ou Instagram)')),
        ('publish_at', models.DateTimeField(default=django.utils.timezone.now, verbose_name='Publicado a partir de')),
        ('published', models.BooleanField(default=False, verbose_name='Visível no site')),
        ('featured', models.BooleanField(default=False, verbose_name='Destaque')),
        ('created_at', models.DateTimeField(auto_now_add=True)),
        ('updated_at', models.DateTimeField(auto_now=True)),
    ], options={'verbose_name':'Vídeo do Vlog','verbose_name_plural':'Vídeos do Vlog','ordering':('-publish_at','-created_at')})]
