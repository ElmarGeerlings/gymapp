from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workouts', '0014_workout_visibility'),
    ]

    operations = [
        migrations.AddField(
            model_name='exerciseset',
            name='is_completed',
            field=models.BooleanField(default=False),
        ),
    ]
