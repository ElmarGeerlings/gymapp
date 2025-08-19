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

    def get_all_names(self):
        """Get all possible names for this exercise (main name + alternatives)"""
        names = [self.name.lower()]
        names.extend([alt.name.lower() for alt in self.alternative_names.all()])
        return names

    def matches_name(self, search_name):
        """Check if this exercise matches the given name (case-insensitive)"""
        search_name = search_name.lower().strip()

        # Direct match with main name
        if self.name.lower() == search_name:
            return True

        # Check alternative names
        for alt_name in self.alternative_names.all():
            if alt_name.name.lower() == search_name:
                return True

        # Fuzzy matching - check if search name contains or is contained in any name
        for name in self.get_all_names():
            if search_name in name or name in search_name:
                return True

        return False


class ExerciseAlternativeName(models.Model):
    """Alternative names for exercises to improve matching"""
    exercise = models.ForeignKey(Exercise, on_delete=models.CASCADE, related_name='alternative_names')
    name = models.CharField(max_length=200)
    is_primary = models.BooleanField(default=False, help_text="If True, this is the main alternative name")

    class Meta:
        unique_together = ['exercise', 'name']
        verbose_name_plural = "Exercise Alternative Names"

    def __str__(self):
        return f"{self.exercise.name} - {self.name}"