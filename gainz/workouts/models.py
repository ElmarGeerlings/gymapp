from django.db import models
from django.conf import settings
from gainz.exercises.models import Exercise
from decimal import Decimal
import math
from typing import Dict, Optional

# -- Program and Routine Planning Models --

class Program(models.Model):
    """ Represents a collection of routines, forming a structured training program. """
    SCHEDULING_CHOICES = [
        ('weekly', 'Weekly'),       # Routines are assigned to specific days of the week.
        ('sequential', 'Sequential'), # Routines are performed in a specific order, regardless of day.
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    is_public = models.BooleanField(default=False) # For future sharing
    is_active = models.BooleanField(default=False)
    scheduling_type = models.CharField(
        max_length=10,
        choices=SCHEDULING_CHOICES,
        default='weekly'
    )

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.is_active:
            # Deactivate other active programs for the same user
            Program.objects.filter(user=self.user, is_active=True).exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)

# Days of week choices, can be moved to a common utils if used elsewhere
DAYS_OF_WEEK_CHOICES = [
    (0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'),
    (3, 'Thursday'), (4, 'Friday'), (5, 'Saturday'), (6, 'Sunday'),
]

class ProgramRoutine(models.Model):
    """ Intermediate model to link Program and Routine with order and day assignment. """
    program = models.ForeignKey(Program, related_name='program_routines', on_delete=models.CASCADE)
    routine = models.ForeignKey('Routine', related_name='program_associations', on_delete=models.CASCADE)
    order = models.PositiveIntegerField(help_text="Order of the routine within the program (e.g., 1, 2, 3). Used if not assigning by day.")
    assigned_day = models.IntegerField(choices=DAYS_OF_WEEK_CHOICES, null=True, blank=True, help_text="Specific day of the week this routine is scheduled for in this program.")

    class Meta:
        ordering = ['program', 'order', 'assigned_day']
        # unique_together = ('program', 'routine') # Removed this constraint
        # A program can't have two routines on the same day, if day is assigned
        # constraints = [
        #     models.UniqueConstraint(fields=['program', 'assigned_day'], condition=models.Q(assigned_day__isnull=False), name='unique_program_assigned_day')
        # ] # This constraint might be too restrictive if order is also used. Let's omit for now.

    def __str__(self):
        day_str = f" (Day: {self.get_assigned_day_display()})" if self.assigned_day is not None else ""
        return f"{self.program.name} - {self.routine.name} (Order: {self.order}){day_str}"

class Routine(models.Model):
    """ Represents a specific reusable workout structure (template). """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

class RoutineExercise(models.Model):
    """ Defines an exercise within a routine, including targets and progression info. """
    routine = models.ForeignKey(Routine, related_name='exercises', on_delete=models.CASCADE)
    exercise = models.ForeignKey('exercises.Exercise', on_delete=models.CASCADE)
    order = models.IntegerField(default=0)
    # target_sets = models.PositiveIntegerField()
    # target_reps = models.CharField(max_length=50) # e.g., "5", "8-12", "AMRAP"
    # target_rest_seconds = models.PositiveIntegerField(null=True, blank=True)
    routine_specific_exercise_type = models.CharField(
        max_length=20, # Adjusted to match Exercise.exercise_type max_length
        choices=Exercise.EXERCISE_TYPE_CHOICES, # Assuming Exercise model is imported
        blank=True,
        null=True,
        help_text="Override the default exercise type for this routine."
    )

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.routine.name} - {self.exercise.name}"

class RoutineExerciseSet(models.Model):
    """ Represents a planned set for an exercise within a routine. """
    routine_exercise = models.ForeignKey(RoutineExercise, related_name='planned_sets', on_delete=models.CASCADE)
    set_number = models.PositiveIntegerField()
    target_reps = models.CharField(max_length=50, blank=True, help_text='e.g., "8-12", "AMRAP", "5"') # Reps can be a range or specific
    target_weight = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    target_rpe = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True, help_text="Rate of Perceived Exertion (e.g., 7.5)")
    rest_time_seconds = models.PositiveIntegerField(null=True, blank=True, help_text="Rest time in seconds after this set")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['set_number']
        # Unique together to ensure set numbers are unique per routine_exercise
        unique_together = ('routine_exercise', 'set_number')

    def __str__(self):
        return f"{self.routine_exercise.exercise.name} - Set {self.set_number}"

# -- Workout Logging Models --

class Workout(models.Model):
    """ Represents a single logged workout session. """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    date = models.DateTimeField()
    name = models.CharField(max_length=200)
    notes = models.TextField(blank=True)
    duration = models.DurationField(null=True, blank=True)
    routine_source = models.ForeignKey(
        Routine,
        related_name='workout_logs',
        on_delete=models.SET_NULL, # Keep log if routine deleted
        null=True,
        blank=True
    )
    
    # Social features
    VISIBILITY_CHOICES = [
        ('public', 'Public'),
        ('private', 'Private'),
    ]
    visibility = models.CharField(
        max_length=10,
        choices=VISIBILITY_CHOICES,
        default='public',
        help_text="Who can see this workout"
    )

    def __str__(self):
        return f"{self.name} - {self.date.strftime('%Y-%m-%d')}"
    
    def is_public(self):
        """Check if workout is public"""
        return self.visibility == 'public'
    
    def can_be_viewed_by(self, user):
        """Check if user can view this workout"""
        if self.user == user:
            return True  # Owner can always view
        return self.is_public()
    
    def get_like_count(self):
        """Get total number of likes for this workout"""
        return self.likes.count() if hasattr(self, 'likes') else 0
    
    def get_comment_count(self):
        """Get total number of comments for this workout"""
        return self.comments.count() if hasattr(self, 'comments') else 0
    
    def is_liked_by(self, user):
        """Check if user has liked this workout"""
        if not user.is_authenticated:
            return False
        return self.likes.filter(user=user).exists() if hasattr(self, 'likes') else False

class WorkoutExercise(models.Model):
    """ Represents a specific exercise performed during a logged workout. """
    FEEDBACK_CHOICES = [
        ('increase', 'Increase'),
        ('stay', 'Stay'),
        ('decrease', 'Decrease'),
    ]
    # Existing choices retained from original file
    EXERCISE_TYPE_CHOICES = [
        ('primary', 'Primary'),
        ('secondary', 'Secondary'),
        ('accessory', 'Accessory'),
    ]

    workout = models.ForeignKey(Workout, related_name='exercises', on_delete=models.CASCADE)
    exercise = models.ForeignKey('exercises.Exercise', on_delete=models.CASCADE)
    order = models.IntegerField(default=0)
    notes = models.TextField(blank=True) # Notes for this specific performance
    exercise_type = models.CharField(
        max_length=20,
        choices=EXERCISE_TYPE_CHOICES,
        null=True,
        blank=True
    )  # If null, use the exercise's default type
    routine_exercise_source = models.ForeignKey(
        RoutineExercise,
        related_name='workout_exercise_logs',
        on_delete=models.SET_NULL, # Keep log if routine exercise definition changes
        null=True,
        blank=True
    )
    performance_feedback = models.CharField(
        max_length=10,
        choices=FEEDBACK_CHOICES,
        null=True,
        blank=True
    )

    class Meta:
        ordering = ['order']

    def get_exercise_type(self):
        """Return the exercise type, falling back to the exercise's default if not specified"""
        return self.exercise_type or self.exercise.exercise_type

    def __str__(self):
        # Adding a basic __str__ for WorkoutExercise
        return f"{self.workout} - {self.exercise.name}"

class ExerciseSet(models.Model):
    """ Represents a single set performed for a WorkoutExercise. """
    workout_exercise = models.ForeignKey(WorkoutExercise, related_name='sets', on_delete=models.CASCADE)
    set_number = models.PositiveIntegerField()
    reps = models.PositiveIntegerField(null=True, blank=True)
    weight = models.DecimalField(max_digits=6, decimal_places=2)
    is_warmup = models.BooleanField(default=False)
    is_completed = models.BooleanField(default=False)
    # AMRAP support: when True, reps is logged later and may be null at creation/edit time
    is_amrap = models.BooleanField(default=False)

    def __str__(self):
        # Adding a basic __str__ for ExerciseSet
        return f"Set {self.set_number} for {self.workout_exercise}"
    
    def calculate_1rm_epley(self) -> Decimal:
        """Calculate 1RM using Epley formula - best for 1-5 reps"""
        if self.reps == 1:
            return self.weight
        return self.weight * (1 + Decimal('0.0333') * self.reps)
    
    def calculate_1rm_brzycki(self) -> Decimal:
        """Calculate 1RM using Brzycki formula - best for 6-10 reps"""
        if self.reps == 1:
            return self.weight
        return self.weight / (Decimal('1.0278') - Decimal('0.0278') * self.reps)
    
    def calculate_1rm_lombardi(self) -> Decimal:
        """Calculate 1RM using Lombardi formula"""
        if self.reps == 1:
            return self.weight
        return self.weight * (Decimal(str(self.reps)) ** Decimal('0.10'))
    
    def calculate_1rm_mcglothin(self) -> Decimal:
        """Calculate 1RM using McGlothin formula"""
        if self.reps == 1:
            return self.weight
        return self.weight * (1 + Decimal('0.025') * self.reps)
    
    def calculate_1rm_wathen(self) -> Decimal:
        """Calculate 1RM using Wathen formula - most accurate overall"""
        if self.reps == 1:
            return self.weight
        exp_term = Decimal(str(math.exp(-0.075 * self.reps)))
        return self.weight * (Decimal('48.8') + Decimal('53.8') * exp_term) / 100
    
    def get_best_1rm_estimate(self) -> Optional[Decimal]:
        """Return most accurate 1RM estimate based on rep range"""
        if not self.is_valid_for_1rm():
            return None
            
        if self.reps == 1:
            return self.weight
        elif 2 <= self.reps <= 5:
            return self.calculate_1rm_epley()
        elif 6 <= self.reps <= 10:
            return self.calculate_1rm_brzycki()
        elif 11 <= self.reps <= 15:
            return self.calculate_1rm_brzycki()
        else:
            return None  # Unreliable for >15 reps
    
    def get_all_1rm_estimates(self) -> Dict[str, Optional[Decimal]]:
        """Return all 1RM calculations for comparison"""
        if not self.is_valid_for_1rm():
            return {}
            
        return {
            'epley': self.calculate_1rm_epley(),
            'brzycki': self.calculate_1rm_brzycki(),
            'lombardi': self.calculate_1rm_lombardi(),
            'mcglothin': self.calculate_1rm_mcglothin(),
            'wathen': self.calculate_1rm_wathen(),
            'best_estimate': self.get_best_1rm_estimate(),
        }
    
    def get_rep_range_category(self) -> str:
        """Return 'low' (1-3), 'mid' (4-6), 'high' (7+)"""
        if not isinstance(self.reps, int):
            return 'high'
        if 1 <= self.reps <= 3:
            return 'low'
        elif 4 <= self.reps <= 6:
            return 'mid'
        else:
            return 'high'
    
    def is_valid_for_1rm(self) -> bool:
        """Check if set is valid for 1RM calculation"""
        return (
            not self.is_warmup and 
            self.weight > 0 and 
            isinstance(self.reps, int) and
            self.reps > 0 and 
            self.reps <= 15
        )
    
    def get_volume(self) -> Decimal:
        """Calculate volume (sets × reps × weight) for this set"""
        if not isinstance(self.reps, int):
            return Decimal('0')
        return self.reps * self.weight

# -- Timer Preference Models --

class UserTimerPreference(models.Model):
    """ User's default timer preferences for different exercise types """
    WEIGHT_UNIT_CHOICES = [
        ('kg', 'Kilograms'),
        ('lbs', 'Pounds'),
    ]
    
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='timer_preferences')
    primary_timer_seconds = models.PositiveIntegerField(default=180, help_text="Default rest timer for primary exercises in seconds")
    secondary_timer_seconds = models.PositiveIntegerField(default=120, help_text="Default rest timer for secondary exercises in seconds")
    accessory_timer_seconds = models.PositiveIntegerField(default=90, help_text="Default rest timer for accessory exercises in seconds")
    auto_start_timer = models.BooleanField(default=False, help_text="Automatically start timer after logging a set")
    timer_sound_enabled = models.BooleanField(default=True, help_text="Play sound when timer completes")
    preferred_weight_unit = models.CharField(
        max_length=3,
        choices=WEIGHT_UNIT_CHOICES,
        default='kg',
        help_text="Preferred unit for displaying and entering weights"
    )
    
    # Auto-progression preferences
    auto_progression_enabled = models.BooleanField(default=False, help_text="Automatically adjust weights/reps based on performance feedback")
    default_weight_increment = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=2.5,
        help_text="Default weight increment for auto-progression (e.g., 2.5 kg/lbs)"
    )
    default_rep_increment = models.PositiveIntegerField(
        default=1,
        help_text="Default rep increment for auto-progression when weight can't be increased"
    )

    class Meta:
        verbose_name = "User Timer Preference"
        verbose_name_plural = "User Timer Preferences"

    def __str__(self):
        return f"Timer preferences for {self.user.username}"

class ExerciseTimerOverride(models.Model):
    """ User-specific timer overrides for individual exercises """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='exercise_timer_overrides')
    exercise = models.ForeignKey('exercises.Exercise', on_delete=models.CASCADE)
    timer_seconds = models.PositiveIntegerField(help_text="Custom rest timer for this exercise in seconds")

    class Meta:
        verbose_name = "Exercise Timer Override"
        verbose_name_plural = "Exercise Timer Overrides"
        unique_together = ('user', 'exercise')

    def __str__(self):
        return f"{self.user.username} - {self.exercise.name} ({self.timer_seconds}s)"

class PersonalRecord(models.Model):
    """ Tracks personal records for exercises with optional video proof """
    RECORD_TYPE_CHOICES = [
        ('1rm', '1 Rep Max'),
        ('volume', 'Volume Record'),
        ('endurance', 'Endurance Record'),
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='personal_records')
    exercise = models.ForeignKey('exercises.Exercise', on_delete=models.CASCADE, related_name='records')
    record_type = models.CharField(max_length=20, choices=RECORD_TYPE_CHOICES, default='1rm')
    
    # Core record data
    weight = models.DecimalField(max_digits=6, decimal_places=2, help_text="Weight used for the record")
    reps = models.PositiveIntegerField(help_text="Reps achieved for the record")
    
    # Metadata
    date_achieved = models.DateTimeField(auto_now_add=True)
    workout_exercise_source = models.ForeignKey(
        WorkoutExercise,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='personal_records_achieved',
        help_text="The workout exercise that achieved this record"
    )
    
    # Optional video upload
    video = models.FileField(
        upload_to='personal_records/videos/%Y/%m/',
        null=True,
        blank=True,
        help_text="Optional video proof of the personal record"
    )
    
    notes = models.TextField(blank=True, help_text="Additional notes about this record")
    
    class Meta:
        verbose_name = "Personal Record"
        verbose_name_plural = "Personal Records"
        unique_together = ('user', 'exercise', 'record_type')
        ordering = ['-date_achieved']
        
    def __str__(self):
        return f"{self.user.username} - {self.exercise.name} {self.record_type}: {self.weight}kg x {self.reps}"
    
    def get_estimated_1rm(self):
        """Calculate estimated 1RM using Brzycki formula"""
        if self.reps == 1:
            return self.weight
        # Brzycki formula: 1RM = weight / (1.0278 - 0.0278 × reps)
        return self.weight / (1.0278 - 0.0278 * self.reps)

class ProgramTimerPreference(models.Model):
    """ Program-specific timer preferences for the highest level of timer customization """
    program = models.OneToOneField(Program, on_delete=models.CASCADE, related_name='timer_preferences')
    primary_timer_seconds = models.PositiveIntegerField(null=True, blank=True, help_text="Program-specific timer for primary exercises in seconds")
    secondary_timer_seconds = models.PositiveIntegerField(null=True, blank=True, help_text="Program-specific timer for secondary exercises in seconds")
    accessory_timer_seconds = models.PositiveIntegerField(null=True, blank=True, help_text="Program-specific timer for accessory exercises in seconds")
    auto_start_timer = models.BooleanField(null=True, blank=True, help_text="Program-specific auto-start timer preference")

    class Meta:
        verbose_name = "Program Timer Preference"
        verbose_name_plural = "Program Timer Preferences"

    def __str__(self):
        return f"Timer preferences for program: {self.program.name}"

class RoutineTimerPreference(models.Model):
    """ Routine-specific timer preferences for granular timer customization """
    routine = models.OneToOneField(Routine, on_delete=models.CASCADE, related_name='timer_preferences')
    primary_timer_seconds = models.PositiveIntegerField(null=True, blank=True, help_text="Routine-specific timer for primary exercises in seconds")
    secondary_timer_seconds = models.PositiveIntegerField(null=True, blank=True, help_text="Routine-specific timer for secondary exercises in seconds")
    accessory_timer_seconds = models.PositiveIntegerField(null=True, blank=True, help_text="Routine-specific timer for accessory exercises in seconds")
    auto_start_timer = models.BooleanField(null=True, blank=True, help_text="Routine-specific auto-start timer preference")

    class Meta:
        verbose_name = "Routine Timer Preference"
        verbose_name_plural = "Routine Timer Preferences"

    def __str__(self):
        return f"Timer preferences for routine: {self.routine.name}"
