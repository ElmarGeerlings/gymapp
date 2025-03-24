from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db import models
from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from gainz.exercises.models import Exercise, ExerciseCategory
from gainz.exercises.serializers import ExerciseSerializer, ExerciseCategorySerializer
from gainz.workouts.models import Workout, WorkoutExercise, ExerciseSet
from gainz.workouts.serializers import WorkoutSerializer, WorkoutExerciseSerializer, ExerciseSetSerializer

# Exercise ViewSets
class ExerciseCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ExerciseCategory.objects.all()
    serializer_class = ExerciseCategorySerializer
    permission_classes = [IsAuthenticated]

class ExerciseViewSet(viewsets.ModelViewSet):
    serializer_class = ExerciseSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Exercise.objects.filter(
            models.Q(is_custom=False) | 
            models.Q(is_custom=True, user=self.request.user)
        )

    def perform_create(self, serializer):
        serializer.save(user=self.request.user, is_custom=True)

# Workout ViewSets
class WorkoutViewSet(viewsets.ModelViewSet):
    serializer_class = WorkoutSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Workout.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=['post'])
    def add_exercise(self, request, pk=None):
        workout = self.get_object()
        serializer = WorkoutExerciseSerializer(data=request.data)
        
        if serializer.is_valid():
            serializer.save(workout=workout)
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class WorkoutExerciseViewSet(viewsets.ModelViewSet):
    serializer_class = WorkoutExerciseSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return WorkoutExercise.objects.filter(workout__user=self.request.user)

class ExerciseSetViewSet(viewsets.ModelViewSet):
    serializer_class = ExerciseSetSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return ExerciseSet.objects.filter(workout_exercise__workout__user=self.request.user)
    
    def perform_create(self, serializer):
        workout_exercise_id = self.kwargs.get('workout_exercise_id')
        if workout_exercise_id:
            workout_exercise = get_object_or_404(
                WorkoutExercise, 
                id=workout_exercise_id,
                workout__user=self.request.user
            )
            
            # Get the next set number
            last_set = ExerciseSet.objects.filter(workout_exercise=workout_exercise).order_by('-set_number').first()
            next_set_number = 1 if not last_set else last_set.set_number + 1
            
            serializer.save(
                workout_exercise=workout_exercise,
                set_number=next_set_number
            )
        else:
            serializer.save()

# Template Views
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
    
    # Get available exercises for the add exercise form
    available_exercises = Exercise.objects.filter(
        models.Q(is_custom=False) | 
        models.Q(is_custom=True, user=request.user)
    )
    
    context = {
        'workout': workout,
        'primary_exercises': primary_exercises,
        'secondary_exercises': secondary_exercises,
        'accessory_exercises': accessory_exercises,
        'available_exercises': available_exercises,
    }
    
    return render(request, 'workout_detail.html', context)

def home(request):
    """Homepage view that redirects to the workout list or shows a welcome page"""
    if request.user.is_authenticated:
        # If user is logged in, you could show their recent workouts
        # or redirect to a workout list page when you create one
        return render(request, 'home.html', {
            'title': 'Gainz - Workout Tracker'
        })
    else:
        # For non-logged in users, show a welcome page
        return render(request, 'home.html', {
            'title': 'Welcome to Gainz'
        })

@login_required
def workout_list(request):
    """Display a list of the user's workouts"""
    workouts = Workout.objects.filter(user=request.user).order_by('-date')
    
    context = {
        'workouts': workouts,
        'title': 'My Workouts'
    }
    
    return render(request, 'workout_list.html', context)

@login_required
def exercise_list(request):
    """Display a list of exercises organized by category"""
    # Get all categories with their exercises
    categories = ExerciseCategory.objects.prefetch_related('exercises').all()
    
    # Get uncategorized exercises
    uncategorized = Exercise.objects.filter(category__isnull=True)
    
    context = {
        'categories': categories,
        'uncategorized': uncategorized,
        'title': 'Exercise Library'
    }
    
    return render(request, 'exercise_list.html', context)