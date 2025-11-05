from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workouts', '0015_exerciseset_is_completed'),
    ]

    operations = [
        migrations.AddField(
            model_name='exerciseset',
            name='is_amrap',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='exerciseset',
            name='reps',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
    ]

