from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('clinic', '0002_remove_payment')]
    operations = [
        migrations.AlterField(model_name='user',name='email',field=models.EmailField(max_length=254,unique=True)),
        migrations.AlterField(model_name='user',name='is_active',field=models.BooleanField(default=True,help_text='Designates whether this user should be treated as active. Unselect this instead of deleting accounts.',verbose_name='active')),
    ]
