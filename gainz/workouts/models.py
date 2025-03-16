from django.db import models
from django.conf import settings
from gainz.exercises.models import Exercise
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required

class Workout(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    date = models.DateTimeField()
    name = models.CharField(max_length=200)
    notes = models.TextField(blank=True)
    duration = models.DurationField(null=True, blank=True)

    def __str__(self):
        return f"{self.name} - {self.date.strftime('%Y-%m-%d')}"

class WorkoutExercise(models.Model):
    EXERCISE_TYPE_CHOICES = [
        ('primary', 'Primary'),
        ('secondary', 'Secondary'),
        ('accessory', 'Accessory'),
    ]
    
    workout = models.ForeignKey(Workout, related_name='exercises', on_delete=models.CASCADE)
    exercise = models.ForeignKey('exercises.Exercise', on_delete=models.CASCADE)
    order = models.IntegerField(default=0)
    notes = models.TextField(blank=True)
    exercise_type = models.CharField(
        max_length=20, 
        choices=EXERCISE_TYPE_CHOICES,
        null=True, 
        blank=True
    )  # If null, use the exercise's default type

    class Meta:
        ordering = ['order']
        
    def get_exercise_type(self):
        """Return the exercise type, falling back to the exercise's default if not specified"""
        return self.exercise_type or self.exercise.exercise_type

class ExerciseSet(models.Model):
    workout_exercise = models.ForeignKey(WorkoutExercise, related_name='sets', on_delete=models.CASCADE)
    set_number = models.IntegerField()
    reps = models.IntegerField()
    weight = models.DecimalField(max_digits=6, decimal_places=2)
    is_warmup = models.BooleanField(default=False)

@login_required
def workout_detail(request, workout_id):
    workout = get_object_or_404(Workout, id=workout_id, user=request.user)
    
    # Group exercises by type
    primary_exercises = []
    secondary_exercises = []
    accessory_exercises = []
    
    for workout_exercise in workout.exercises.all():
        exercise_type = workout_exercise.get_exercise_type()
        if exercise_type == 'primary':
            primary_exercises.append(workout_exercise)
        elif exercise_type == 'secondary':
            secondary_exercises.append(workout_exercise)
        else:
            accessory_exercises.append(workout_exercise)
    
    context = {
        'workout': workout,
        'primary_exercises': primary_exercises,
        'secondary_exercises': secondary_exercises,
        'accessory_exercises': accessory_exercises,
    }
    
    return render(request, 'workouts/workout_detail.html', context) 