from django.db import models
from django.conf import settings # Added import for settings

class ExerciseCategory(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = "Exercise Categories"

    def __str__(self):
        return self.name

class Exercise(models.Model):
    EXERCISE_TYPE_CHOICES = [
        ('primary', 'Primary'),
        ('secondary', 'Secondary'),
        ('accessory', 'Accessory'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, # Or models.CASCADE if custom exercises should be deleted with user
        null=True,
        blank=True,
        related_name='custom_exercises' # Added related_name
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    categories = models.ManyToManyField(
        ExerciseCategory,
        related_name='exercises',
        blank=True # Allows exercises to have no category
    )
    is_custom = models.BooleanField(default=False)  # For user-created exercises
    exercise_type = models.CharField(
        max_length=20,
        choices=EXERCISE_TYPE_CHOICES,
        default='accessory'
    )

    def __str__(self):
        return self.name