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

    def __str__(self):
        return self.name

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
    target_sets = models.PositiveIntegerField()
    target_reps = models.CharField(max_length=50) # e.g., "5", "8-12", "AMRAP"
    target_rest_seconds = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.routine.name} - {self.exercise.name}"

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