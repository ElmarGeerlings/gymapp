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
    
    BODYPART_CHOICES = [
        ('chest', 'Chest'),
        ('back', 'Back'),
        ('shoulders', 'Shoulders'),
        ('arms', 'Arms'),
        ('legs', 'Legs'),
        ('glutes', 'Glutes'),
        ('core', 'Core'),
        ('cardio', 'Cardio'),
        ('full_body', 'Full Body'),
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
    primary_bodypart = models.CharField(
        max_length=20,
        choices=BODYPART_CHOICES,
        null=True,
        blank=True,
        help_text="Primary muscle group targeted by this exercise"
    )
    secondary_bodypart = models.CharField(
        max_length=20,
        choices=BODYPART_CHOICES,
        null=True,
        blank=True,
        help_text="Secondary muscle group targeted by this exercise"
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

    def get_timer_duration_for_user(self, user):
        """
        Get the appropriate timer duration for this exercise for a specific user.
        
        Priority order:
        1. User-specific exercise timer override
        2. User's default timer preference for exercise type
        3. System defaults (180s for primary, 120s for secondary, 90s for accessory)
        """
        # Check for user-specific override first
        try:
            override = user.exercise_timer_overrides.get(exercise=self)
            return override.timer_seconds
        except:
            pass
        
        # Fall back to user's default preferences for exercise type
        try:
            preferences = user.timer_preferences
            if self.exercise_type == 'primary':
                return preferences.primary_timer_seconds
            elif self.exercise_type == 'secondary':
                return preferences.secondary_timer_seconds
            else:  # accessory
                return preferences.accessory_timer_seconds
        except:
            pass
        
        # Final fallback to system defaults
        if self.exercise_type == 'primary':
            return 180
        elif self.exercise_type == 'secondary':
            return 120
        else:  # accessory
            return 90

    def get_auto_start_timer_setting(self, user):
        """
        Get the auto-start timer setting for this user.
        Returns False if user has no preferences set.
        """
        try:
            return user.timer_preferences.auto_start_timer
        except:
            return False

    def get_timer_sound_setting(self, user):
        """
        Get the timer sound setting for this user.
        Returns True if user has no preferences set (default enabled).
        """
        try:
            return user.timer_preferences.timer_sound_enabled
        except:
            return True


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