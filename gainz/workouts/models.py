from django.db import models
from django.conf import settings
from gainz.exercises.models import Exercise

# -- Program and Routine Planning Models --

class Program(models.Model):
    """ Represents a collection of routines, forming a structured training program. """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    is_public = models.BooleanField(default=False) # For future sharing
    is_active = models.BooleanField(default=False)

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
        unique_together = ('program', 'routine') # A routine can only be in a program once
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

    def __str__(self):
        return f"{self.name} - {self.date.strftime('%Y-%m-%d')}"

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
    reps = models.PositiveIntegerField()
    weight = models.DecimalField(max_digits=6, decimal_places=2)
    is_warmup = models.BooleanField(default=False)

    def __str__(self):
        # Adding a basic __str__ for ExerciseSet
        return f"Set {self.set_number} for {self.workout_exercise}"