from django.db import models

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
    
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.ForeignKey(ExerciseCategory, on_delete=models.CASCADE)
    is_custom = models.BooleanField(default=False)  # For user-created exercises
    exercise_type = models.CharField(
        max_length=20, 
        choices=EXERCISE_TYPE_CHOICES,
        default='accessory'
    )

    def __str__(self):
        return self.name