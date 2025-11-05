from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('exercises', '0005_auto_20250909_2346'),
    ]

    operations = [
        migrations.AddField(
            model_name='exercise',
            name='weight_increment',
            field=models.DecimalField(blank=True, decimal_places=1, help_text='Weight increment in kg for this exercise (e.g., 1.0, 2.5)', max_digits=4, null=True),
        ),
    ]

