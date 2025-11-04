from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db import models, transaction
from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from gainz.exercises.models import Exercise, ExerciseCategory
from gainz.exercises.serializers import ExerciseSerializer, ExerciseCategorySerializer
from gainz.workouts.models import Workout, WorkoutExercise, ExerciseSet, Program, Routine, RoutineExercise, RoutineExerciseSet, ProgramRoutine, UserTimerPreference, ExerciseTimerOverride, ProgramTimerPreference, RoutineTimerPreference
from gainz.workouts.serializers import WorkoutSerializer, WorkoutExerciseSerializer, ExerciseSetSerializer
from django.http import JsonResponse, HttpResponse, HttpResponseBadRequest, HttpResponseForbidden, Http404, FileResponse
from django.template.loader import render_to_string
from django.db.models import Q
import datetime # Add datetime import
from gainz.workouts.utils import get_prefill_data # Add get_prefill_data import
from django.utils import timezone # Added for timezone.now()
from django.urls import reverse # Add import for reverse
from django.contrib import messages # Added for messages
from django.core.cache import cache # Added for Redis cache
import statistics
from collections import defaultdict
from django.contrib.staticfiles import finders
from django.contrib.staticfiles.storage import staticfiles_storage
import json # Moved import json here
from datetime import timedelta
from django.contrib.auth.models import User
from django.contrib.auth import login
from django.core.management import call_command
from io import StringIO
from gainz.workouts.utils import WorkoutParser
from decimal import Decimal
from django.db.models import F, Sum, Min, Max, Avg
from .utils.progress_tracking import (
    get_progress_metrics, analyze_strength_trends,
    get_top_exercises_by_volume, get_exercise_progress,
    get_personal_records_summary, get_personal_records
)

# Make Redis optional for deployments without Redis
def get_redis_connection():
    try:
        # Use django_redis which respects our SSL configuration in settings.py
        from django_redis import get_redis_connection as django_redis_conn
        return django_redis_conn("default")
    except:
        return None

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

    def perform_update(self, serializer):
        # Only allow updating custom exercises owned by the user
        exercise = self.get_object()
        if not exercise.is_custom or exercise.user != self.request.user:
            raise PermissionDenied("You can only edit your own custom exercises.")
        serializer.save()

    def perform_destroy(self, instance):
        # Only allow deleting custom exercises owned by the user
        if not instance.is_custom or instance.user != self.request.user:
            raise PermissionDenied("You can only delete your own custom exercises.")
        instance.delete()

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

    @action(detail=True, methods=['post'], url_path='reorder-exercises')
    def reorder_exercises(self, request, pk=None):
        workout = self.get_object()
        exercises_data = request.data.get('exercises', [])

        if not exercises_data:
            return Response({'error': 'No exercises data provided'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            for exercise_data in exercises_data:
                exercise_id = exercise_data.get('id')
                new_order = exercise_data.get('order')

                if exercise_id and new_order is not None:
                    WorkoutExercise.objects.filter(
                        id=exercise_id,
                        workout=workout
                    ).update(order=new_order)

            return Response({'success': True, 'message': 'Exercise order updated successfully'})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

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

    # Fetch WorkoutExercises related to this workout, prefetching related Exercise and Sets
    # Order by the order field to respect user's custom ordering
    workout_exercises = workout.exercises.prefetch_related('exercise', 'sets').order_by('order')

    # Group exercises by type using the get_exercise_type method
    primary_exercises = []
    secondary_exercises = []
    accessory_exercises = []

    for workout_exercise in workout_exercises:
        exercise_type = workout_exercise.get_exercise_type()
        if exercise_type == 'primary':
            primary_exercises.append(workout_exercise)
        elif exercise_type == 'secondary':
            secondary_exercises.append(workout_exercise)
        else: # Default or accessory
            accessory_exercises.append(workout_exercise)

    # Get all exercises for the add exercise dropdown
    all_exercises_for_form = Exercise.objects.filter(
        models.Q(is_custom=False) |
        models.Q(is_custom=True, user=request.user)
    ).order_by('name')

    # Get exercise type choices for the dropdown
    exercise_type_choices = Exercise.EXERCISE_TYPE_CHOICES

    context = {
        'workout': workout,
        'primary_exercises': primary_exercises,
        'secondary_exercises': secondary_exercises,
        'accessory_exercises': accessory_exercises,
        'all_exercises_for_form': all_exercises_for_form,
        'exercise_type_choices': exercise_type_choices,
        'title': f"Workout: {workout.name}" # Added a title for the page
    }

    # Check for device_type cookie to determine template
    device_type = request.COOKIES.get('device_type')
    template_name = 'workout_detail_mobile.html' if device_type == 'mobile' else 'workout_detail.html'

    return render(request, template_name, context)

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

    # Build routine options for "Choose" modal
    active_program = Program.objects.filter(user=request.user, is_active=True).first()
    active_program_routines = []
    if active_program:
        active_program_routines = [
            pr.routine for pr in ProgramRoutine.objects.filter(program=active_program)
            .select_related('routine').order_by('order')
        ]

    # All user routines
    all_user_routines = Routine.objects.filter(user=request.user).order_by('name')
    # Routines not in active program (if any)
    other_routines = all_user_routines.exclude(id__in=[r.id for r in active_program_routines])

    context = {
        'workouts': workouts,
        'title': 'My Workouts',
        'active_program': active_program,
        'active_program_routines': active_program_routines,
        'other_routines': other_routines,
    }

    return render(request, 'workout_list.html', context)

@login_required
def exercise_list(request):
    """Display a list of exercises organized by category and provide data for the add modal."""

    search_query = request.GET.get('search_query', '')
    exercise_type_filter = request.GET.get('exercise_type', '')
    category_filter = request.GET.get('category', '')
    custom_filter = request.GET.get('custom_filter', '')

    exercises = Exercise.objects.prefetch_related('categories').select_related('user').order_by('name')

    if search_query:
        exercises = exercises.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query)
        )

    if exercise_type_filter:
        exercises = exercises.filter(exercise_type=exercise_type_filter)

    if category_filter:
        exercises = exercises.filter(categories__id=category_filter)

    # Apply custom filter
    if custom_filter == 'custom':
        exercises = exercises.filter(is_custom=True, user=request.user)
    elif custom_filter == 'non_custom':
        exercises = exercises.filter(is_custom=False)
    else:
        # Default: show all exercises (non-custom and user's custom)
        exercises = exercises.filter(Q(is_custom=False) | Q(is_custom=True, user=request.user))

    exercises_by_category = {}
    uncategorized_exercises = []
    for exercise in exercises:
        if exercise.categories.exists():
            for category in exercise.categories.all():
                if category.name not in exercises_by_category:
                    exercises_by_category[category.name] = []
                if exercise not in exercises_by_category[category.name]:
                   exercises_by_category[category.name].append(exercise)
        else:
            uncategorized_exercises.append(exercise)

    sorted_categories_list = sorted(exercises_by_category.items())

    all_categories_for_form = ExerciseCategory.objects.all().order_by('name')
    exercise_type_choices = Exercise.EXERCISE_TYPE_CHOICES

    context = {
        'grouped_exercises': sorted_categories_list,
        'uncategorized': uncategorized_exercises,
        'categories_for_form': all_categories_for_form,
        'exercise_types_for_form': exercise_type_choices,
        'title': 'Exercise Library',
        'current_search_query': search_query,
        'current_exercise_type': exercise_type_filter,
        'current_category': category_filter,
        'current_custom_filter': custom_filter,
        'request': request
    }

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        # For AJAX requests, render only the partial and return as HTML
        html = render_to_string('partials/_exercise_list_items.html', context, request=request)
        return HttpResponse(html)

    # For regular GET requests, render the full page
    return render(request, 'exercise_list.html', context)

@login_required
def routine_list(request):
    """Display routines with optional filtering by program.

    Default: if a program is active, show routines from that program (and select it in the dropdown).
    If no active program, show all routines and select "All Routines".
    Supports `?program=all` or `?program=<id>` to filter explicitly.
    """
    programs = Program.objects.filter(user=request.user).order_by('name')
    active_program = programs.filter(is_active=True).first()

    program_param = request.GET.get('program')  # 'all' | <program_id>
    selected_program = None

    # Determine routines queryset
    if program_param == 'all':
        routines = Routine.objects.filter(user=request.user).order_by('name')
        current_program_filter = 'all'
    elif program_param and program_param.isdigit():
        selected_program = programs.filter(id=int(program_param)).first()
        if selected_program:
            routines = Routine.objects.filter(
                user=request.user,
                program_associations__program=selected_program
            ).distinct().order_by('name')
            current_program_filter = str(selected_program.id)
        else:
            # Invalid program id: fall back to default logic
            if active_program:
                selected_program = active_program
                routines = Routine.objects.filter(
                    user=request.user,
                    program_associations__program=selected_program
                ).distinct().order_by('name')
                current_program_filter = str(selected_program.id)
            else:
                routines = Routine.objects.filter(user=request.user).order_by('name')
                current_program_filter = 'all'
    else:
        # Default: use active program if present; otherwise show all
        if active_program:
            selected_program = active_program
            routines = Routine.objects.filter(
                user=request.user,
                program_associations__program=selected_program
            ).distinct().order_by('name')
            current_program_filter = str(selected_program.id)
        else:
            routines = Routine.objects.filter(user=request.user).order_by('name')
            current_program_filter = 'all'

    # Title hint
    if selected_program:
        title = f'Routines in: {selected_program.name}'
    elif current_program_filter == 'all':
        title = 'All Routines'
    else:
        title = 'Your Routines'

    context = {
        'programs': programs,
        'routines': routines,
        'selected_program': selected_program,
        'current_program_filter': current_program_filter,
        'title': title,
    }
    return render(request, 'routine_list.html', context)

@login_required
def routine_detail(request, routine_id):
    """Display the details of a specific routine and its exercises."""
    routine = get_object_or_404(Routine, id=routine_id, user=request.user)
    # Fetch routine exercises, ordered, and prefetch the related exercise object
    # to avoid extra DB queries in the template.
    routine_exercises = routine.exercises.select_related('exercise').order_by('order')

    context = {
        'routine': routine,
        'routine_exercises': routine_exercises,
        'title': f"Routine: {routine.name}"
    }
    return render(request, 'routine_detail.html', context)

@login_required
def routine_create(request):
    all_exercises_qs = Exercise.objects.filter(Q(is_custom=False) | Q(is_custom=True, user=request.user)).order_by('name')
    all_exercises_for_template = [
        {"pk": ex.pk, "name": ex.name, "default_type_display": ex.get_exercise_type_display()} for ex in all_exercises_qs
    ]
    exercise_type_choices = Exercise.EXERCISE_TYPE_CHOICES

    user_id = request.user.id
    redis_conn = get_redis_connection()
    user_preferences = {}
    preference_definitions = {
        'show_rpe': {'key_suffix': 'routineForm.showRPE', 'default': False},
        'show_rest_time': {'key_suffix': 'routineForm.showRestTime', 'default': False},
        'show_notes': {'key_suffix': 'routineForm.showNotes', 'default': False},
    }

    for pref_name, pref_info in preference_definitions.items():
        cache_key = f"user_prefs:{user_id}:{pref_info['key_suffix']}"
        # REVERTED: No more hardcoded key for RPE loading
        # if pref_name == 'show_rpe':
        #     cache_key = f"test_rpe_preference_user_{user_id}"

        if redis_conn:
            retrieved_value_bytes = redis_conn.get(cache_key)
            if retrieved_value_bytes is not None:
                retrieved_value_str = retrieved_value_bytes.decode('utf-8')
                user_preferences[pref_name] = retrieved_value_str.lower() == 'true'
            else:
                user_preferences[pref_name] = pref_info['default']
        else:
            user_preferences[pref_name] = pref_info['default']

    if request.method == 'POST':
        try:
            with transaction.atomic(): # Wrap in a transaction
                routine_name = request.POST.get('name')
                routine_description = request.POST.get('description')

                if not routine_name:
                    raise ValueError("Routine name is required.")

                routine = Routine.objects.create(
                    user=request.user,
                    name=routine_name,
                    description=routine_description,
                )

                # Process RoutineExercises and their PlannedSets
                exercise_idx = 0
                while True:
                    exercise_pk_key = f'routine_exercise_{exercise_idx}_exercise_pk'
                    if exercise_pk_key not in request.POST:
                        break # No more exercises

                    exercise_pk = request.POST.get(exercise_pk_key)
                    order = request.POST.get(f'routine_exercise_{exercise_idx}_order', exercise_idx)
                    specific_type = request.POST.get(f'routine_exercise_{exercise_idx}_routine_specific_exercise_type', '')

                    if not exercise_pk: # Skip if no exercise selected for this card
                        exercise_idx += 1
                        continue

                    exercise_instance = get_object_or_404(Exercise, pk=exercise_pk)

                    routine_exercise = RoutineExercise.objects.create(
                        routine=routine,
                        exercise=exercise_instance,
                        order=int(order),
                        routine_specific_exercise_type=specific_type if specific_type else None
                    )

                    # Process PlannedSets for this RoutineExercise
                    set_idx = 0
                    while True:
                        set_reps_key = f'routine_exercise_{exercise_idx}_planned_sets_{set_idx}_target_reps'
                        # Check for a core field, e.g., target_reps or set_number hidden input
                        set_number_val = request.POST.get(f'routine_exercise_{exercise_idx}_planned_sets_{set_idx}_set_number')

                        if set_number_val is None: # No more sets for this exercise or placeholder was not submitted
                            # A more robust check might be for presence of any set field for this index
                            # For now, assuming if set_number is not there, the set is not intended to be saved.
                            break

                        target_reps = request.POST.get(set_reps_key, '')
                        target_weight = request.POST.get(f'routine_exercise_{exercise_idx}_planned_sets_{set_idx}_target_weight')
                        target_rpe = request.POST.get(f'routine_exercise_{exercise_idx}_planned_sets_{set_idx}_target_rpe')
                        rest_seconds = request.POST.get(f'routine_exercise_{exercise_idx}_planned_sets_{set_idx}_rest_time_seconds')
                        notes = request.POST.get(f'routine_exercise_{exercise_idx}_planned_sets_{set_idx}_notes', '')

                        RoutineExerciseSet.objects.create(
                            routine_exercise=routine_exercise,
                            set_number=int(set_number_val),
                            target_reps=target_reps,
                            target_weight=target_weight if target_weight else None,
                            target_rpe=target_rpe if target_rpe else None,
                            rest_time_seconds=rest_seconds if rest_seconds else None,
                            notes=notes
                        )
                        set_idx += 1
                    exercise_idx += 1

                return redirect('routine-detail', routine_id=routine.id)
        except Exception as e:
            # Handle error: (e.g., log it, show a generic error message)
            context = {
                'title': 'Create New Routine',
                'all_exercises': all_exercises_for_template,
                'exercise_type_choices': exercise_type_choices,
                'user_preferences': user_preferences,
                'error': str(e), # Display the error for debugging, refine for production
                # Consider re-populating form with request.POST data here
                'form_data': request.POST # Pass POST data back to re-fill form
            }
            return render(request, 'routine_form.html', context, status=400)

    context = {
        'title': 'Create New Routine',
        'all_exercises': all_exercises_for_template,
        'exercise_type_choices': exercise_type_choices,
        'user_preferences': user_preferences,
    }
    return render(request, 'routine_form.html', context)

@login_required
def routine_update(request, routine_id):
    routine = get_object_or_404(Routine, id=routine_id, user=request.user)
    routine_exercises = routine.exercises.select_related('exercise').prefetch_related('planned_sets').order_by('order')
    all_exercises_qs = Exercise.objects.filter(Q(is_custom=False) | Q(is_custom=True, user=request.user)).order_by('name')
    all_exercises_for_template = [
        {"pk": ex.pk, "name": ex.name, "default_type_display": ex.get_exercise_type_display()} for ex in all_exercises_qs
    ]
    exercise_type_choices = Exercise.EXERCISE_TYPE_CHOICES

    user_id = request.user.id
    redis_conn = get_redis_connection()
    user_preferences = {}
    preference_definitions = {
        'show_rpe': {'key_suffix': 'routineForm.showRPE', 'default': False},
        'show_rest_time': {'key_suffix': 'routineForm.showRestTime', 'default': False},
        'show_notes': {'key_suffix': 'routineForm.showNotes', 'default': False},
    }

    for pref_name, pref_info in preference_definitions.items():
        cache_key = f"user_prefs:{user_id}:{pref_info['key_suffix']}"
        # REVERTED: No more hardcoded key for RPE loading
        # if pref_name == 'show_rpe':
        #     cache_key = f"test_rpe_preference_user_{user_id}"

        if redis_conn:
            retrieved_value_bytes = redis_conn.get(cache_key)
            if retrieved_value_bytes is not None:
                retrieved_value_str = retrieved_value_bytes.decode('utf-8')
                user_preferences[pref_name] = retrieved_value_str.lower() == 'true'
            else:
                user_preferences[pref_name] = pref_info['default']
        else:
            user_preferences[pref_name] = pref_info['default']

    print(f"[routine_update] User preferences: {user_preferences}") # Your existing debug print
    context = {
        'title': f'Edit Routine: {routine.name}',
        'object': routine,
        'routine_exercises': routine_exercises,
        'all_exercises': all_exercises_for_template,
        'exercise_type_choices': Exercise.EXERCISE_TYPE_CHOICES,
        'user_preferences': user_preferences,
    }

    if request.method == 'POST':
        try:
            with transaction.atomic(): # Wrap in a transaction
                routine.name = request.POST.get('name', routine.name)
                routine.description = request.POST.get('description', routine.description)
                if not routine.name:
                    raise ValueError("Routine name cannot be empty.")
                routine.save()

                processed_routine_exercise_ids = set()
                exercise_idx = 0
                while True:
                    exercise_pk_key = f'routine_exercise_{exercise_idx}_exercise_pk'
                    if exercise_pk_key not in request.POST:
                        break

                    routine_exercise_id = request.POST.get(f'routine_exercise_{exercise_idx}_id')
                    exercise_pk = request.POST.get(exercise_pk_key)
                    order = request.POST.get(f'routine_exercise_{exercise_idx}_order', exercise_idx)
                    specific_type = request.POST.get(f'routine_exercise_{exercise_idx}_routine_specific_exercise_type', '')

                    if not exercise_pk: # Skip if no exercise selected
                        # If it had an ID, it might mean it was an existing RE card whose exercise was cleared.
                        # This RE should be deleted if it exists.
                        if routine_exercise_id:
                            try:
                                old_re = RoutineExercise.objects.get(id=routine_exercise_id, routine=routine)
                                old_re.delete() # Delete it as it's no longer valid (no exercise selected)
                            except RoutineExercise.DoesNotExist:
                                pass # Was never saved or already deleted
                        exercise_idx += 1
                        continue

                    exercise_instance = get_object_or_404(Exercise, pk=exercise_pk)

                    current_re = None
                    if routine_exercise_id:
                        try:
                            current_re = RoutineExercise.objects.get(id=routine_exercise_id, routine=routine)
                            current_re.exercise = exercise_instance
                            current_re.order = int(order)
                            current_re.routine_specific_exercise_type = specific_type if specific_type else None
                            current_re.save()
                        except RoutineExercise.DoesNotExist:
                            # ID was present but not found, treat as new, or could be an error
                            current_re = None # Fall through to create

                    if not current_re: # Create new if no ID or ID not found
                        current_re = RoutineExercise.objects.create(
                            routine=routine,
                            exercise=exercise_instance,
                            order=int(order),
                            routine_specific_exercise_type=specific_type if specific_type else None
                        )
                    processed_routine_exercise_ids.add(current_re.id)

                    # Process PlannedSets for this RoutineExercise
                    processed_set_ids = set()
                    set_idx = 0
                    while True:
                        set_id_key = f'routine_exercise_{exercise_idx}_planned_sets_{set_idx}_id'
                        set_number_val = request.POST.get(f'routine_exercise_{exercise_idx}_planned_sets_{set_idx}_set_number')

                        if set_number_val is None: # No more sets for this exercise
                            break

                        set_id = request.POST.get(set_id_key)
                        target_reps = request.POST.get(f'routine_exercise_{exercise_idx}_planned_sets_{set_idx}_target_reps', '')
                        target_weight = request.POST.get(f'routine_exercise_{exercise_idx}_planned_sets_{set_idx}_target_weight')
                        target_rpe = request.POST.get(f'routine_exercise_{exercise_idx}_planned_sets_{set_idx}_target_rpe')
                        rest_seconds = request.POST.get(f'routine_exercise_{exercise_idx}_planned_sets_{set_idx}_rest_time_seconds')
                        notes = request.POST.get(f'routine_exercise_{exercise_idx}_planned_sets_{set_idx}_notes', '')

                        current_set = None
                        if set_id:
                            try:
                                current_set = RoutineExerciseSet.objects.get(id=set_id, routine_exercise=current_re)
                                current_set.set_number = int(set_number_val)
                                current_set.target_reps = target_reps
                                current_set.target_weight = target_weight if target_weight else None
                                current_set.target_rpe = target_rpe if target_rpe else None
                                current_set.rest_time_seconds = rest_seconds if rest_seconds else None
                                current_set.notes = notes
                                current_set.save()
                            except RoutineExerciseSet.DoesNotExist:
                                current_set = None # Fall through to create

                        if not current_set: # Create new set
                            current_set = RoutineExerciseSet.objects.create(
                                routine_exercise=current_re,
                                set_number=int(set_number_val),
                                target_reps=target_reps,
                                target_weight=target_weight if target_weight else None,
                                target_rpe=target_rpe if target_rpe else None,
                                rest_time_seconds=rest_seconds if rest_seconds else None,
                                notes=notes
                            )
                        processed_set_ids.add(current_set.id)
                        set_idx += 1

                    # Delete sets for this RE that were not in the submission
                    set_ids_to_delete = set(current_re.planned_sets.values_list('id', flat=True)) - processed_set_ids
                    if set_ids_to_delete:
                        RoutineExerciseSet.objects.filter(id__in=set_ids_to_delete, routine_exercise=current_re).delete()

                    exercise_idx += 1

                # Delete RoutineExercises that were not in the submission
                re_ids_to_delete = set(routine.exercises.values_list('id', flat=True)) - processed_routine_exercise_ids
                if re_ids_to_delete:
                    RoutineExercise.objects.filter(id__in=re_ids_to_delete, routine=routine).delete()

                return redirect('routine-detail', routine_id=routine.id)
        except Exception as e:
            context = {
                'title': f'Edit Routine: {routine.name}',
                'object': routine,
                'routine_exercises': routine.exercises.prefetch_related('exercise', 'planned_sets').select_related('exercise').order_by('order'),
                'all_exercises': all_exercises_for_template,
                'exercise_type_choices': Exercise.EXERCISE_TYPE_CHOICES,
                'user_preferences': user_preferences,
                'error': str(e), # Display the error for debugging
                'form_data': request.POST # Pass POST data back
            }
            return render(request, 'routine_form.html', context, status=400)

    routine_exercises_qs = routine.exercises.prefetch_related(
        'exercise',
        'planned_sets'
    ).select_related('exercise').order_by('order')

    context = {
        'title': f'Edit Routine: {routine.name}',
        'object': routine,
        'routine_exercises': routine_exercises_qs,
        'all_exercises': all_exercises_for_template,
        'exercise_type_choices': Exercise.EXERCISE_TYPE_CHOICES,
        'user_preferences': user_preferences,
    }
    return render(request, 'routine_form.html', context)

@login_required
def routine_delete(request, routine_id):
    routine = get_object_or_404(Routine, id=routine_id, user=request.user)
    if request.method == 'POST':
        routine.delete()
        return redirect('routine-list')
    return render(request, 'routine_confirm_delete.html', {
        'object': routine,
        'title': f'Delete Routine: {routine.name}'
    })

@login_required
def program_create(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description')
        is_active = request.POST.get('is_active') == 'on' # Checkbox value

        if not name:
            # Handle error: name is required
            context = {
                'title': 'Create New Program',
                'error': 'Program name is required.',
                'name_value': name,
                'description_value': description,
                'is_active_value': is_active
            }
            return render(request, 'program_form.html', context, status=400)

        program = Program.objects.create(
            user=request.user,
            name=name,
            description=description,
            is_active=is_active # This will trigger the custom save method
        )
        # If creating the first program, or if is_active is checked, it handles activation.
        # If no programs were active and this one isn't checked, it remains inactive.
        # If it's the *only* program, we might want to auto-activate it.
        if Program.objects.filter(user=request.user).count() == 1:
            program.is_active = True # Ensure the first program is active
            program.save() # Save again to trigger potential deactivation of others (though none here)

        return redirect('program-list') # Redirect to the program list
    else:
        # Check if this will be the first program for the user to auto-check 'is_active'
        is_first_program = not Program.objects.filter(user=request.user).exists()
        context = {
            'title': 'Create New Program',
            'is_active_value': is_first_program # Pre-check if it's the first one
        }
    return render(request, 'program_form.html', context)

@login_required
def program_update(request, program_id):
    program = get_object_or_404(Program, id=program_id, user=request.user)

    if request.method == 'POST':
        with transaction.atomic():
            old_scheduling_type = program.scheduling_type
            new_scheduling_type = request.POST.get('scheduling_type', 'weekly')

            program.name = request.POST.get('name', program.name)
            program.description = request.POST.get('description', program.description)
            program.is_active = request.POST.get('is_active') == 'on'
            program.scheduling_type = new_scheduling_type
            program.save()

            # If scheduling type changed, preserve routines but adjust their structure
            if old_scheduling_type != new_scheduling_type:
                existing_routines = list(program.program_routines.select_related('routine').order_by('order', 'assigned_day').all())
                program.program_routines.all().delete()

                if new_scheduling_type == 'sequential':
                    # Convert from weekly to sequential - preserve order
                    for i, program_routine in enumerate(existing_routines):
                        ProgramRoutine.objects.create(
                            program=program,
                            routine=program_routine.routine,
                            order=i + 1,
                            assigned_day=None
                        )
                else:  # Converting to weekly
                    # Convert from sequential to weekly - distribute across days
                    days = [0, 1, 2, 3, 4, 5, 6]  # Monday to Sunday
                    for i, program_routine in enumerate(existing_routines):
                        assigned_day = days[i % len(days)]  # Cycle through days
                        # Check if there's already a routine on this day and adjust order
                        existing_on_day = ProgramRoutine.objects.filter(
                            program=program,
                            assigned_day=assigned_day
                        ).count()
                        ProgramRoutine.objects.create(
                            program=program,
                            routine=program_routine.routine,
                            order=existing_on_day + 1,  # Proper order within the day
                            assigned_day=assigned_day
                        )
            else:
                # Same scheduling type - process normal updates
                program.program_routines.all().delete()

                if program.scheduling_type == 'weekly':
                    # Process weekly schedule
                    for day_val, day_name in ProgramRoutine._meta.get_field('assigned_day').choices:
                        routine_ids = request.POST.getlist(f'weekly_day_{day_val}_routines')
                        for i, r_id in enumerate(routine_ids):
                            routine = get_object_or_404(Routine, id=r_id, user=request.user)
                            ProgramRoutine.objects.create(
                                program=program,
                                routine=routine,
                                assigned_day=day_val,
                                order=i + 1 # Order within the day
                            )
                else: # Sequential
                    # Process sequential schedule
                    i = 0
                    while f'program_routine_{i}_routine_id' in request.POST:
                        routine_id = request.POST.get(f'program_routine_{i}_routine_id')
                        order = request.POST.get(f'program_routine_{i}_order')
                        if routine_id and order:
                            routine = get_object_or_404(Routine, id=routine_id, user=request.user)
                            ProgramRoutine.objects.create(
                                program=program,
                                routine=routine,
                                order=int(order),
                                assigned_day=None
                            )
                        i += 1

            # If scheduling type changed, redirect back to edit page to show the converted routines
            if old_scheduling_type != new_scheduling_type:
                messages.success(request, f'Program converted from {old_scheduling_type} to {new_scheduling_type} scheduling. Routines have been automatically rearranged.')
                return redirect('program-update', program_id=program.id)
            else:
                return redirect('program-list')

    # GET request logic remains the same
    all_user_routines = Routine.objects.filter(user=request.user)
    # Exclude routines already in the program from the "add" dropdown
    assigned_routine_pks = program.program_routines.values_list('routine__pk', flat=True)
    available_routines = all_user_routines.exclude(pk__in=assigned_routine_pks)

    context = {
        'title': f'Edit Program: {program.name}',
        'object': program,
        'is_active_value': program.is_active,
        'program_routines': program.program_routines.select_related('routine').order_by('order', 'assigned_day'),
        'available_routines': available_routines,
        'day_choices': ProgramRoutine._meta.get_field('assigned_day').choices
    }
    return render(request, 'program_form.html', context)

@login_required
def program_delete(request, program_id):
    program = get_object_or_404(Program, id=program_id, user=request.user)
    if request.method == 'POST':
        program.delete()
        return redirect('program-list')
    context = {
        'object': program,
        'title': f'Delete Program: {program.name}'
    }
    return render(request, 'program_confirm_delete.html', context)

@login_required
def program_list(request):
    programs = Program.objects.filter(user=request.user).prefetch_related(
        'program_routines__routine__exercises__exercise',
        'program_routines__routine__exercises__planned_sets'
    ).order_by('-is_active', 'name')
    context = {
        'programs': programs,
        'title': 'Your Programs'
    }
    return render(request, 'program_list.html', context)

@login_required
def program_activate(request, program_id):
    program = get_object_or_404(Program, id=program_id, user=request.user)
    program.is_active = True
    program.save()
    messages.success(request, f'"{program.name}" has been activated.')
    return redirect('program-list')

@login_required
def program_deactivate(request, program_id):
    program = get_object_or_404(Program, id=program_id, user=request.user)
    program.is_active = False
    program.save()
    messages.success(request, f'"{program.name}" has been deactivated.')
    return redirect('program-list')

@login_required
def start_workout_from_routine(request, routine_id):
    """
    Directly creates a workout from a routine and redirects to the workout detail page.
    Skips the intermediate form page.
    """
    routine = get_object_or_404(Routine, id=routine_id, user=request.user)
    today = datetime.date.today()

    # Auto-generate workout name: "Routine Name #X"
    completed_count = Workout.objects.filter(user=request.user, routine_source=routine).count()
    workout_name = f"{routine.name} #{completed_count + 1}"

    # Determine last workout for this routine (to clone if present)
    last_workout = Workout.objects.filter(
        user=request.user,
        routine_source=routine
    ).order_by('-date').first()

    # Create the Workout instance
    new_workout = Workout.objects.create(
        user=request.user,
        name=workout_name,
        notes="",
        date=datetime.datetime.now(),
        routine_source=routine
    )

    if last_workout:
        # Clone last session structure: exercises and sets, preserving order and links
        for prev_we in last_workout.exercises.prefetch_related('sets', 'exercise').order_by('order'):
            new_we = WorkoutExercise.objects.create(
                workout=new_workout,
                exercise=prev_we.exercise,
                order=prev_we.order,
                notes="",  # do not copy notes
                routine_exercise_source=prev_we.routine_exercise_source,
                exercise_type=prev_we.exercise_type,
                performance_feedback=prev_we.performance_feedback
            )
            for prev_set in prev_we.sets.all().order_by('set_number'):
                ExerciseSet.objects.create(
                    workout_exercise=new_we,
                    set_number=prev_set.set_number,
                    reps=prev_set.reps,
                    weight=prev_set.weight,
                    is_warmup=prev_set.is_warmup
                )
        return redirect('workout-detail', workout_id=new_workout.id)
    else:
        # First time with this routine: use planned template + prefill
        for routine_exercise in routine.exercises.prefetch_related('planned_sets', 'exercise').order_by('order'):
            # Create WorkoutExercise based on routine exercise
            workout_exercise = WorkoutExercise.objects.create(
                workout=new_workout,
                exercise=routine_exercise.exercise,
                order=routine_exercise.order,
                notes="",
                routine_exercise_source=routine_exercise,
                exercise_type=routine_exercise.routine_specific_exercise_type or routine_exercise.exercise.exercise_type
            )

            # Create sets based on planned sets with intelligent prefill
            for set_template in routine_exercise.planned_sets.all().order_by('set_number'):
                prefill = get_prefill_data(request.user, set_template, today)
                reps = prefill.get('reps', 0) or 0
                weight = prefill.get('weight', 0) or 0

                ExerciseSet.objects.create(
                    workout_exercise=workout_exercise,
                    set_number=set_template.set_number,
                    reps=reps,
                    weight=weight,
                    is_warmup=set_template.is_warmup if hasattr(set_template, 'is_warmup') else False
                )

        return redirect('workout-detail', workout_id=new_workout.id)

@login_required
def start_empty_workout(request):
    """
    Creates an empty workout without any routine and redirects to the workout detail page.
    Users can add exercises manually on the detail page.
    """
    # Count total workouts for naming
    workout_count = Workout.objects.filter(user=request.user).count()

    # Create empty workout
    new_workout = Workout.objects.create(
        user=request.user,
        name=f"Workout #{workout_count + 1}",
        notes="",
        date=datetime.datetime.now(),
        routine_source=None  # No routine source for freestyle workout
    )

    # Redirect to the workout detail page where user can add exercises
    return redirect('workout-detail', workout_id=new_workout.id)

@login_required
def clear_workout(request, workout_id):
    """
    Removes all exercises from an existing workout.
    """
    workout = get_object_or_404(Workout, id=workout_id, user=request.user)

    if request.method == 'POST':
        # Delete all workout exercises (this will cascade delete all sets)
        workout.exercises.all().delete()

        # Clear the routine source to make it a freestyle workout
        workout.routine_source = None
        workout.save()

        # Redirect back to the workout detail page
        return redirect('workout-detail', workout_id=workout.id)

    # If not POST, redirect to workout detail
    return redirect('workout-detail', workout_id=workout.id)

@login_required
def workout_update(request, workout_id):
    workout = get_object_or_404(Workout, id=workout_id, user=request.user)

    if request.method == 'POST':
        # Basic update for Workout model fields for now
        workout.name = request.POST.get('name', workout.name)
        workout.notes = request.POST.get('notes', workout.notes)
        date_str = request.POST.get('date')
        if date_str:
            try:
                # Assuming date is submitted in YYYY-MM-DD HH:MM:SS or YYYY-MM-DD format
                # Adjust parsing as needed based on form input type
                parsed_date = datetime.datetime.fromisoformat(date_str)
                workout.date = parsed_date
            except ValueError:
                # Handle invalid date format, perhaps add an error to the form
                pass # For now, keep original date if parsing fails

        duration_str = request.POST.get('duration')
        if duration_str: # Django's DurationField can parse various formats like "HH:MM:SS" or "X days, HH:MM:SS"
            try:
                # Example: parsing "HH:MM" or "HH:MM:SS"
                parts = list(map(int, duration_str.split(':')))
                if len(parts) == 2:
                    workout.duration = datetime.timedelta(hours=parts[0], minutes=parts[1])
                elif len(parts) == 3:
                    workout.duration = datetime.timedelta(hours=parts[0], minutes=parts[1], seconds=parts[2])
                # Add more parsing logic if needed or use a duration widget in form
            except (ValueError, TypeError):
                pass # Keep original if parsing fails

        workout.save()
        # Add success message
        return redirect('workout-detail', workout_id=workout.id)

    context = {
        'object': workout,
        'title': f'Edit Workout: {workout.name}'
    }
    return render(request, 'workout_form.html', context)

@login_required
def workout_delete(request, workout_id):
    workout = get_object_or_404(Workout, id=workout_id, user=request.user)
    if request.method == 'POST':
        workout.delete()
        # If AJAX request, return JSON instead of redirect
        is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST.get('ajax') == '1'
        if is_ajax:
            return JsonResponse({'status': 'success'})
        # Fallback to redirect for non-AJAX
        return redirect('workout-list')

    context = {
        'object': workout, # Using 'object' for consistency with other delete views
        'title': f'Delete Workout: {workout.name}'
    }
    return render(request, 'workout_confirm_delete.html', context)

@login_required
def ajax_update_program_scheduling(request, program_id):
    """
    AJAX endpoint to update program scheduling type and convert routines between weekly and sequential
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST requests allowed'}, status=405)

    try:
        program = get_object_or_404(Program, id=program_id, user=request.user)

        # Parse JSON body
        import json
        data = json.loads(request.body)
        new_scheduling_type = data.get('scheduling_type')
        current_routines = data.get('routines', None)  # Get current state from frontend

        if new_scheduling_type not in ['weekly', 'sequential']:
            return JsonResponse({'error': 'Invalid scheduling type'}, status=400)

        old_scheduling_type = program.scheduling_type

        if old_scheduling_type == new_scheduling_type:
            return JsonResponse({'success': True, 'message': 'No change needed'})

        with transaction.atomic():
            program.scheduling_type = new_scheduling_type
            program.save()

            # If frontend provides current routines state, use that instead of auto-converting
            if current_routines:
                # Clear existing program routines
                program.program_routines.all().delete()

                # Re-create based on frontend state
                if new_scheduling_type == 'weekly':
                    # current_routines should be a dict with day numbers as keys
                    for day_str, routines in current_routines.items():
                        day_num = int(day_str)
                        for idx, routine_data in enumerate(routines):
                            routine_id = routine_data.get('routine_id')
                            if routine_id:
                                try:
                                    routine = Routine.objects.get(id=routine_id, user=request.user)
                                    ProgramRoutine.objects.create(
                                        program=program,
                                        routine=routine,
                                        assigned_day=day_num,
                                        order=idx + 1
                                    )
                                except Routine.DoesNotExist:
                                    continue
                else:  # sequential
                    # current_routines should be a list
                    for idx, routine_data in enumerate(current_routines):
                        routine_id = routine_data.get('routine_id')
                        if routine_id:
                            try:
                                routine = Routine.objects.get(id=routine_id, user=request.user)
                                ProgramRoutine.objects.create(
                                    program=program,
                                    routine=routine,
                                    order=idx + 1,
                                    assigned_day=None
                                )
                            except Routine.DoesNotExist:
                                continue
            else:
                # Fallback to auto-conversion if no state provided
                existing_routines = list(program.program_routines.select_related('routine').order_by('order', 'assigned_day').all())

                if new_scheduling_type == 'weekly' and old_scheduling_type == 'sequential':
                    # Converting from sequential to weekly - distribute routines across days
                    days = [0, 1, 2, 3, 4, 5, 6]  # Monday to Sunday
                    for i, pr in enumerate(existing_routines):
                        pr.assigned_day = days[i % 7]  # Distribute evenly across week
                        pr.save()

                elif new_scheduling_type == 'sequential' and old_scheduling_type == 'weekly':
                    # Converting from weekly to sequential - set order based on day and preserve sequence
                    ordered_prs = sorted(existing_routines, key=lambda x: (x.assigned_day or 0, x.order))
                    for i, pr in enumerate(ordered_prs):
                        pr.order = i + 1
                        pr.assigned_day = None  # Clear day assignment
                        pr.save()

        # Return the updated routine assignments
        updated_routines = []
        for pr in program.program_routines.select_related('routine').order_by('order', 'assigned_day'):
            updated_routines.append({
                'id': pr.id,
                'routine_id': pr.routine.id,
                'routine_name': pr.routine.name,
                'order': pr.order,
                'assigned_day': pr.assigned_day
            })

        return JsonResponse({
            'success': True,
            'message': f'Successfully converted to {new_scheduling_type} scheduling',
            'routines': updated_routines,
            'scheduling_type': new_scheduling_type
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def ajax_restore_program_state(request, program_id):
    """
    AJAX endpoint to restore program to a previous state
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST requests allowed'}, status=405)

    try:
        program = get_object_or_404(Program, id=program_id, user=request.user)

        # Parse JSON body
        import json
        data = json.loads(request.body)
        original_state = data.get('original_state')

        if not original_state:
            return JsonResponse({'error': 'No original state provided'}, status=400)

        with transaction.atomic():
            # Restore scheduling type
            program.scheduling_type = original_state.get('scheduling_type', 'sequential')
            program.save()

            # Clear existing program routines
            program.program_routines.all().delete()

            # Restore routines based on scheduling type
            if program.scheduling_type == 'weekly':
                weekly_routines = original_state.get('weekly_routines', {})
                for day, routines in weekly_routines.items():
                    day_num = int(day)
                    for routine_data in routines:
                        routine_id = routine_data.get('routine_id')
                        if routine_id:
                            try:
                                routine = Routine.objects.get(id=routine_id, user=request.user)
                                ProgramRoutine.objects.create(
                                    program=program,
                                    routine=routine,
                                    assigned_day=day_num,
                                    order=routine_data.get('order', 0)
                                )
                            except Routine.DoesNotExist:
                                continue
            else:  # sequential
                sequential_routines = original_state.get('sequential_routines', [])
                for routine_data in sequential_routines:
                    routine_id = routine_data.get('routine_id')
                    if routine_id:
                        try:
                            routine = Routine.objects.get(id=routine_id, user=request.user)
                            ProgramRoutine.objects.create(
                                program=program,
                                routine=routine,
                                order=routine_data.get('order', 0),
                                assigned_day=None
                            )
                        except Routine.DoesNotExist:
                            continue

        return JsonResponse({
            'success': True,
            'message': 'Program state restored successfully'
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def simple_api_test(request):
    """
    A simple API test view that returns a JSON response with an HTML snippet.
    """
    if request.method == 'GET':
        html_content = "<p style='color: green; border: 1px solid green; padding: 5px;'>This HTML came from Python!</p>"
        return JsonResponse({
            'message': 'Hello from Python! API test successful.',
            'status': 'ok',
            'html_snippet': html_content
        })
    return JsonResponse({'error': 'Only GET requests are allowed'}, status=405)

@login_required
def ajax_update_workout_exercise_feedback(request):
    if request.method == 'GET':
        workout_exercise_id = request.GET.get('workoutExerciseId') # Note: JS dataset converts camelCase
        feedback_value = request.GET.get('feedback')

        if not workout_exercise_id or not feedback_value:
            return JsonResponse({
                'error': 'Missing workout_exercise_id or feedback value.',
                'html': 'Error: Missing data.',
                'toast': {
                    'body': 'Required information was missing to update feedback.',
                    'status': 'danger',
                    'title': 'Update Error'
                }
            }, status=400)

        try:
            workout_exercise = WorkoutExercise.objects.select_related(
                'workout_log__workout__user',
                'exercise'
            ).get(id=workout_exercise_id)
        except WorkoutExercise.DoesNotExist:
            return JsonResponse({
                'error': 'WorkoutExercise not found.',
                'html': 'Error: Not found.',
                'toast': {
                    'body': 'The exercise entry could not be found.',
                    'status': 'danger',
                    'title': 'Not Found'
                }
            }, status=404)

        # Permission check
        if workout_exercise.workout_log.workout.user != request.user:
            return JsonResponse({
                'error': 'Permission denied.',
                'html': 'Permission denied.',
                'toast': {
                    'body': 'You do not have permission to update this feedback.',
                    'status': 'danger',
                    'title': 'Forbidden'
                }
            }, status=403)

        # Validate feedback_value
        valid_feedbacks = [choice[0] for choice in WorkoutExercise.PERFORMANCE_FEEDBACK_CHOICES]
        if feedback_value not in valid_feedbacks:
            return JsonResponse({
                'error': 'Invalid feedback value.',
                'html': 'Invalid feedback.',
                'toast': {
                    'body': f'The provided feedback \'{feedback_value}\' is not valid.',
                    'status': 'warning',
                    'title': 'Validation Error'
                }
            }, status=400)

        try:
            workout_exercise.performance_feedback = feedback_value
            workout_exercise.save(update_fields=['performance_feedback'])

            new_feedback_display = workout_exercise.get_performance_feedback_display() or "Not set"

            return JsonResponse({
                'html': new_feedback_display,
                'toast': {
                    'body': 'Performance feedback updated successfully!',
                    'status': 'success',
                    'title': 'Feedback Updated'
                }
            })
        except Exception as e:
            # Log the exception e for server-side debugging
            print(f"Error saving workout exercise feedback: {e}")
            return JsonResponse({
                'error': 'Server error during update.',
                'html': 'Server error.',
                'toast': {
                    'body': 'An unexpected error occurred while saving your feedback.',
                    'status': 'danger',
                    'title': 'Server Error'
                }
            }, status=500)

    return JsonResponse({'error': 'Invalid request method.', 'html': 'Error.'}, status=405)

@login_required
def start_next_workout(request):
    user = request.user
    next_routine = None
    active_program = Program.objects.filter(user=user, is_active=True).first()

    if active_program:
        if active_program.scheduling_type == 'weekly':
            # Weekly schedule logic
            today_weekday = timezone.now().weekday()
            program_routine_today = ProgramRoutine.objects.filter(
                program=active_program,
                assigned_day=today_weekday
            ).select_related('routine').order_by('order').first()
            if program_routine_today:
                next_routine = program_routine_today.routine

        else: # Sequential schedule logic - Smart scheduling for Mon/Wed/Fri/Sun pattern
            # Get the last few workouts to understand the pattern
            recent_workouts = Workout.objects.filter(
                user=user,
                routine_source__program_associations__program=active_program
            ).order_by('-date')[:10]  # Look at last 10 workouts

            # Count how many times each routine has been done this week
            from datetime import timedelta
            week_start = timezone.now().date() - timedelta(days=timezone.now().weekday())
            this_week_workouts = Workout.objects.filter(
                user=user,
                routine_source__program_associations__program=active_program,
                date__gte=week_start
            ).select_related('routine_source')

            # Get all program routines ordered
            all_program_routines = list(ProgramRoutine.objects.filter(
                program=active_program
            ).order_by('order').select_related('routine'))

            if not all_program_routines:
                next_routine = None
            else:
                # Determine expected workout based on day of week pattern (Mon=0, Wed=2, Fri=4, Sun=6)
                today_weekday = timezone.now().weekday()
                days_since_week_start = (timezone.now().date() - week_start).days

                # Map your workout pattern: Mon(0)->A, Wed(2)->B, Fri(4)->C, Sun(6)->D
                expected_workout_map = {
                    0: 0,  # Monday -> routine A (index 0)
                    1: 0,  # Tuesday -> still routine A (in case shifted)
                    2: 1,  # Wednesday -> routine B (index 1)
                    3: 2,  # Thursday -> routine C (in case Friday shifted)
                    4: 2,  # Friday -> routine C (index 2)
                    5: 2,  # Saturday -> routine C (in case Friday shifted)
                    6: 3,  # Sunday -> routine D (index 3)
                }

                # Get expected routine index for today
                expected_index = expected_workout_map.get(today_weekday, 0)

                # But also check what was actually done this week
                completed_this_week = set()
                for workout in this_week_workouts:
                    for i, pr in enumerate(all_program_routines):
                        if pr.routine == workout.routine_source:
                            completed_this_week.add(i)
                            break

                # Find the next routine that hasn't been done this week
                next_routine = None
                for i in range(expected_index, len(all_program_routines)):
                    if i not in completed_this_week and i < len(all_program_routines):
                        next_routine = all_program_routines[i].routine
                        break

                # If nothing found from expected index onwards, or if we're past Sunday,
                # just follow the sequential pattern
                if not next_routine:
                    last_workout = recent_workouts.first() if recent_workouts else None
                    if last_workout and last_workout.routine_source:
                        for i, pr in enumerate(all_program_routines):
                            if pr.routine == last_workout.routine_source:
                                next_index = (i + 1) % len(all_program_routines)
                                next_routine = all_program_routines[next_index].routine
                                break
                    else:
                        # First workout ever
                        next_routine = all_program_routines[0].routine

    if next_routine:
        redirect_url = reverse('start-workout-from-routine', args=[next_routine.id])
        return redirect(f'{redirect_url}?source=smart-start')
    else:
        # Fallback: No routine found, create an ad-hoc workout
        existing_workouts_count = Workout.objects.filter(user=user).count()
        workout_name = f"Workout #{existing_workouts_count + 1}"
        new_workout = Workout.objects.create(
            user=user,
            name=workout_name,
            date=timezone.now()
        )
        return redirect('workout-detail', workout_id=new_workout.id)

@login_required
def update_user_preferences(request):
    if request.method == 'POST':
        user_id = request.user.id
        try:
            data = json.loads(request.body.decode('utf-8'))
            preference_key_suffix = data.get('preference_key')
            preference_value = data.get('preference_value')
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)

        if preference_key_suffix and preference_value is not None:
            cache_key = f"user_prefs:{user_id}:{preference_key_suffix}"
            # REVERTED: No more hardcoded key for RPE saving
            # if preference_key_suffix == 'routineForm.showRPE':
            #     cache_key = f"test_rpe_preference_user_{user_id}"

            redis_conn = get_redis_connection()
            if isinstance(preference_value, bool):
                value_to_store = "true" if preference_value else "false"
            else:
                value_to_store = str(preference_value)

            try:
                if redis_conn:
                    redis_conn.set(cache_key, value_to_store)
                    return JsonResponse({'status': 'success', 'message': 'Preference saved via django-rq.'})
                else:
                    return JsonResponse({'status': 'warning', 'message': 'Redis not available, preference not saved.'})
            except Exception as e:
                return JsonResponse({'status': 'error', 'message': f'Failed to save to Redis: {e}'}, status=500)
        else:
            return JsonResponse({'status': 'error', 'message': 'Missing key or value.'}, status=400)

    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)

@login_required
def api_timer_preferences(request):
    """API endpoint to fetch and save user timer preferences"""
    if request.method == 'GET':
        try:
            # Try to get existing preferences
            timer_prefs, created = UserTimerPreference.objects.get_or_create(
                user=request.user,
                defaults={
                    'primary_timer_seconds': 180,
                    'secondary_timer_seconds': 120,
                    'accessory_timer_seconds': 90,
                    'auto_start_timer': False,
                    'timer_sound_enabled': True,
                    'preferred_weight_unit': 'kg',
                }
            )

            return JsonResponse({
                'primary_timer_seconds': timer_prefs.primary_timer_seconds,
                'secondary_timer_seconds': timer_prefs.secondary_timer_seconds,
                'accessory_timer_seconds': timer_prefs.accessory_timer_seconds,
                'auto_start_timer': timer_prefs.auto_start_timer,
                'timer_sound_enabled': timer_prefs.timer_sound_enabled,
                'preferred_weight_unit': timer_prefs.preferred_weight_unit,
            })

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    elif request.method == 'POST':
        try:
            # Parse JSON data from request body
            data = json.loads(request.body.decode('utf-8'))

            # Get or create user timer preferences
            timer_prefs, created = UserTimerPreference.objects.get_or_create(
                user=request.user,
                defaults={
                    'primary_timer_seconds': 180,
                    'secondary_timer_seconds': 120,
                    'accessory_timer_seconds': 90,
                    'auto_start_timer': False,
                    'timer_sound_enabled': True,
                    'preferred_weight_unit': 'kg',
                }
            )

            # Validate and update fields
            errors = {}

            # Validate primary_timer_seconds (0-3600 seconds)
            if 'primary_timer_seconds' in data:
                try:
                    primary_timer = int(data['primary_timer_seconds'])
                    if 0 <= primary_timer <= 3600:
                        timer_prefs.primary_timer_seconds = primary_timer
                    else:
                        errors['primary_timer_seconds'] = 'Must be between 0 and 3600 seconds'
                except (ValueError, TypeError):
                    errors['primary_timer_seconds'] = 'Must be a valid integer'

            # Validate secondary_timer_seconds (0-3600 seconds)
            if 'secondary_timer_seconds' in data:
                try:
                    secondary_timer = int(data['secondary_timer_seconds'])
                    if 0 <= secondary_timer <= 3600:
                        timer_prefs.secondary_timer_seconds = secondary_timer
                    else:
                        errors['secondary_timer_seconds'] = 'Must be between 0 and 3600 seconds'
                except (ValueError, TypeError):
                    errors['secondary_timer_seconds'] = 'Must be a valid integer'

            # Validate accessory_timer_seconds (0-3600 seconds)
            if 'accessory_timer_seconds' in data:
                try:
                    accessory_timer = int(data['accessory_timer_seconds'])
                    if 0 <= accessory_timer <= 3600:
                        timer_prefs.accessory_timer_seconds = accessory_timer
                    else:
                        errors['accessory_timer_seconds'] = 'Must be between 0 and 3600 seconds'
                except (ValueError, TypeError):
                    errors['accessory_timer_seconds'] = 'Must be a valid integer'

            # Validate auto_start_timer (boolean)
            if 'auto_start_timer' in data:
                if isinstance(data['auto_start_timer'], bool):
                    timer_prefs.auto_start_timer = data['auto_start_timer']
                else:
                    errors['auto_start_timer'] = 'Must be a boolean value'

            # Validate timer_sound_enabled (boolean)
            if 'timer_sound_enabled' in data:
                if isinstance(data['timer_sound_enabled'], bool):
                    timer_prefs.timer_sound_enabled = data['timer_sound_enabled']
                else:
                    errors['timer_sound_enabled'] = 'Must be a boolean value'

            # Validate preferred_weight_unit (choices: kg/lbs)
            if 'preferred_weight_unit' in data:
                valid_units = [choice[0] for choice in UserTimerPreference.WEIGHT_UNIT_CHOICES]
                weight_unit = data['preferred_weight_unit']
                if weight_unit in valid_units:
                    timer_prefs.preferred_weight_unit = weight_unit
                else:
                    errors['preferred_weight_unit'] = f'Must be one of: {", ".join(valid_units)}'

            # Return validation errors if any
            if errors:
                return JsonResponse({
                    'success': False,
                    'error': 'Validation failed',
                    'errors': errors
                }, status=400)

            # Save the updated preferences
            timer_prefs.save()

            # Return success response with updated data
            return JsonResponse({
                'success': True,
                'message': 'Timer preferences updated successfully',
                'data': {
                    'primary_timer_seconds': timer_prefs.primary_timer_seconds,
                    'secondary_timer_seconds': timer_prefs.secondary_timer_seconds,
                    'accessory_timer_seconds': timer_prefs.accessory_timer_seconds,
                    'auto_start_timer': timer_prefs.auto_start_timer,
                    'timer_sound_enabled': timer_prefs.timer_sound_enabled,
                    'preferred_weight_unit': timer_prefs.preferred_weight_unit,
                }
            })

        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON data'
            }, status=400)
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)

    return JsonResponse({'error': 'Only GET and POST requests allowed'}, status=405)

# Health check view for Railway deployment
def health_check(request):
    """Simple health check endpoint for Railway"""
    return HttpResponse("OK", content_type="text/plain")

# Development data generation view (REMOVE IN PRODUCTION!)
@login_required
def generate_sample_data(request):
    """Generate sample data for development purposes only"""
    if request.method == 'POST':
        try:
            # Create a string buffer to capture command output
            out = StringIO()

            # Run both populate commands
            call_command('populate_exercises', stdout=out)
            call_command('populate_data', user=request.user.username, stdout=out)

            # Get the output
            output = out.getvalue()

            messages.success(request, 'Sample data generated successfully!')

            # Return JSON response for AJAX request
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'success',
                    'message': 'Sample data generated successfully!',
                    'output': output
                })

            return redirect('home')

        except Exception as e:
            error_msg = f'Error generating sample data: {str(e)}'
            messages.error(request, error_msg)

            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'error',
                    'message': error_msg
                }, status=500)

            return redirect('home')

    # GET request not allowed for this view
    return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

# User registration view
def register(request):
    """Simple user registration with username and password"""
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        errors = []

        # Basic validation
        if not username:
            errors.append('Username is required.')
        if not password:
            errors.append('Password is required.')

        # Check if username already exists
        if username and User.objects.filter(username=username).exists():
            errors.append('Username already taken.')

        if not errors:
            try:
                # Create user
                user = User.objects.create_user(
                    username=username,
                    password=password
                )
                # Log the user in
                login(request, user)
                messages.success(request, f'Welcome {username}! Your account has been created.')
                return redirect('home')
            except Exception as e:
                errors.append('An error occurred creating your account. Please try again.')

        context = {
            'errors': errors,
            'username': username,
            'title': 'Sign Up'
        }
        return render(request, 'register.html', context)

    context = {
        'title': 'Sign Up'
    }
    return render(request, 'register.html', context)

@login_required
def import_routine(request):
    """Import program from pasted workout text"""
    parser = WorkoutParser()

    if request.method == 'POST':
        program_name = request.POST.get('program_name', '').strip()
        workout_text = request.POST.get('workout_text', '').strip()
        create_missing = request.POST.get('create_missing') == 'on'

        errors = []

        if not program_name:
            errors.append('Program name is required.')
        if not workout_text:
            errors.append('Workout text is required.')

        if not errors:
            try:
                with transaction.atomic():
                    # Parse the workout text into separate days
                    workout_days = parser.parse_workout_days(workout_text)

                    if not workout_days:
                        errors.append('No exercises could be parsed from the text. Please check the format.')
                    else:
                        # Create the program first
                        program = Program.objects.create(
                            user=request.user,
                            name=program_name,
                            description=f'Imported from text on {timezone.now().strftime("%Y-%m-%d %H:%M")}',
                            is_active=not Program.objects.filter(user=request.user, is_active=True).exists(),  # Make active if no other active program
                            scheduling_type='sequential'
                        )

                        total_exercises = 0
                        created_exercises = []
                        skipped_exercises = []
                        routine_names = []

                        # Day names for routines
                        day_names = ['A', 'B', 'C', 'D', 'E', 'F', 'G']

                        for day_index, day_exercises in enumerate(workout_days):
                            if not day_exercises:
                                continue

                            # Create routine for this day
                            day_name = day_names[day_index] if day_index < len(day_names) else f'Day {day_index + 1}'
                            routine_name = f'{program_name} - {day_name}'
                            routine_names.append(routine_name)

                            routine = Routine.objects.create(
                                user=request.user,
                                name=routine_name,
                                description=f'Day {day_index + 1} - Imported on {timezone.now().strftime("%Y-%m-%d %H:%M")}'
                            )

                            # Process each exercise for this day
                            exercise_order = 0

                            for parsed_ex in day_exercises:
                                exercise_name = parsed_ex['exercise_name']

                                # Find or create the exercise
                                exercise = parser.find_or_create_exercise(exercise_name)

                                if not exercise:
                                    if create_missing:
                                        # Create the exercise
                                        exercise = Exercise.objects.create(
                                            name=exercise_name,
                                            description=f'Auto-created from import',
                                            is_custom=True,
                                            user=request.user,
                                            exercise_type='accessory'
                                        )
                                        if exercise_name not in created_exercises:
                                            created_exercises.append(exercise_name)
                                    else:
                                        if exercise_name not in skipped_exercises:
                                            skipped_exercises.append(exercise_name)
                                        continue

                                # Create RoutineExercise
                                routine_exercise = RoutineExercise.objects.create(
                                    routine=routine,
                                    exercise=exercise,
                                    order=exercise_order
                                )
                                exercise_order += 1
                                total_exercises += 1

                                # Create RoutineExerciseSet entries
                                sets = parsed_ex['sets']
                                reps = parsed_ex['reps']
                                weight = parsed_ex['weight']

                                for set_num in range(1, sets + 1):
                                    RoutineExerciseSet.objects.create(
                                        routine_exercise=routine_exercise,
                                        set_number=set_num,
                                        target_reps=reps,
                                        target_weight=Decimal(str(weight)) if weight else None
                                    )

                            # Link routine to program
                            ProgramRoutine.objects.create(
                                program=program,
                                routine=routine,
                                order=day_index + 1
                            )

                        # Success message
                        messages.success(request, f'Program "{program_name}" created with {len(workout_days)} routines ({", ".join(routine_names)}) and {total_exercises} total exercises.')

                        if created_exercises:
                            messages.info(request, f'Created {len(created_exercises)} new exercises: {", ".join(created_exercises)}')

                        if skipped_exercises:
                            messages.warning(request, f'Skipped {len(skipped_exercises)} unknown exercises: {", ".join(skipped_exercises)}')

                        return redirect('program-list')

            except Exception as e:
                errors.append(f'Error importing program: {str(e)}')

        context = {
            'title': 'Import Program',
            'program_name': program_name,
            'workout_text': workout_text,
            'create_missing': create_missing,
            'errors': errors
        }
        return render(request, 'import_routine.html', context)

    # GET request
    context = {
        'title': 'Import Program',
        'sample_format': """OHP 3x5 70
Pull ups 3x10
Triceps 4x10 40
Laterals 4x10 14"""
    }
    return render(request, 'import_routine.html', context)

@login_required
def import_single_routine(request):
    """Import a single Routine from pasted workout text (no Program created)."""
    parser = WorkoutParser()

    if request.method == 'POST':
        routine_name = request.POST.get('routine_name', '').strip()
        workout_text = request.POST.get('workout_text', '').strip()
        create_missing = request.POST.get('create_missing') == 'on'

        errors = []

        if not routine_name:
            errors.append('Routine name is required.')
        if not workout_text:
            errors.append('Workout text is required.')

        if not errors:
            try:
                with transaction.atomic():
                    # Create the routine first
                    routine = Routine.objects.create(
                        user=request.user,
                        name=routine_name,
                        description=f'Imported from text on {timezone.now().strftime("%Y-%m-%d %H:%M")}',
                    )

                    parsed_exercises = parser.parse_workout_text(workout_text)
                    if not parsed_exercises:
                        errors.append('No exercises could be parsed from the text. Please check the format.')
                        # Fall through to render form with error
                    else:
                        created_exercises = []
                        skipped_exercises = []
                        total_exercises = 0
                        exercise_order = 1

                        for parsed_ex in parsed_exercises:
                            exercise_name = parsed_ex['exercise_name']

                            # Find or create the exercise
                            exercise = parser.find_or_create_exercise(exercise_name)

                            if not exercise:
                                if create_missing:
                                    exercise = Exercise.objects.create(
                                        name=exercise_name,
                                        description='Auto-created from import',
                                        is_custom=True,
                                        user=request.user,
                                        exercise_type='accessory'
                                    )
                                    if exercise_name not in created_exercises:
                                        created_exercises.append(exercise_name)
                                else:
                                    if exercise_name not in skipped_exercises:
                                        skipped_exercises.append(exercise_name)
                                    continue

                            # Create RoutineExercise
                            routine_exercise = RoutineExercise.objects.create(
                                routine=routine,
                                exercise=exercise,
                                order=exercise_order
                            )
                            exercise_order += 1
                            total_exercises += 1

                            # Create RoutineExerciseSet entries
                            sets = parsed_ex['sets']
                            reps = parsed_ex['reps']
                            weight = parsed_ex['weight']

                            for set_num in range(1, sets + 1):
                                RoutineExerciseSet.objects.create(
                                    routine_exercise=routine_exercise,
                                    set_number=set_num,
                                    target_reps=reps,
                                    target_weight=Decimal(str(weight)) if weight else None
                                )

                        # Success message
                        messages.success(
                            request,
                            f'Routine "{routine_name}" created with {total_exercises} exercises.'
                        )

                        if created_exercises:
                            messages.info(
                                request,
                                f'Created {len(created_exercises)} new exercises: {", ".join(created_exercises)}'
                            )

                        if skipped_exercises:
                            messages.warning(
                                request,
                                f'Skipped {len(skipped_exercises)} unknown exercises: {", ".join(skipped_exercises)}'
                            )

                        return redirect('routine-detail', routine_id=routine.id)

            except Exception as e:
                errors.append(f'Error importing routine: {str(e)}')

        # Render with errors
        context = {
            'title': 'Import Routine',
            'routine_name': routine_name,
            'workout_text': workout_text,
            'create_missing': create_missing,
            'errors': errors,
        }
        return render(request, 'import_single_routine.html', context)

    # GET request
    context = {
        'title': 'Import Routine',
        'sample_format': """OHP 3x5 70\nPull ups 3x10\nTriceps 4x10 40""",
    }
    return render(request, 'import_single_routine.html', context)

@login_required
def profile(request):
    """User profile view with basic info and timer preferences"""
    user = request.user

    # Get or create user timer preferences
    timer_prefs, created = UserTimerPreference.objects.get_or_create(
        user=user,
        defaults={
            'primary_timer_seconds': 180,
            'secondary_timer_seconds': 120,
            'accessory_timer_seconds': 90,
            'auto_start_timer': False,
            'timer_sound_enabled': True,
            'auto_progression_enabled': False,
            'default_weight_increment': 2.5,
            'default_rep_increment': 1,
        }
    )

    if request.method == 'POST':
        # Handle basic profile update (username and email)
        new_username = request.POST.get('username', '').strip()
        new_email = request.POST.get('email', '').strip()
        preferred_weight_unit = request.POST.get('preferred_weight_unit', 'kg')

        # Get timer preferences
        primary_timer_seconds = request.POST.get('primary_timer_seconds', '180')
        secondary_timer_seconds = request.POST.get('secondary_timer_seconds', '120')
        accessory_timer_seconds = request.POST.get('accessory_timer_seconds', '90')
        auto_start_timer = request.POST.get('auto_start_timer') == '1'
        timer_sound_enabled = request.POST.get('timer_sound_enabled') == '1'

        # Get auto-progression preferences
        auto_progression_enabled = request.POST.get('auto_progression_enabled') == '1'
        default_weight_increment = request.POST.get('default_weight_increment', '2.5')
        default_rep_increment = request.POST.get('default_rep_increment', '1')

        errors = []

        if not new_username:
            errors.append('Username is required.')
        elif new_username != user.username and User.objects.filter(username=new_username).exists():
            errors.append('Username already taken.')

        # Validate weight unit choice
        valid_units = [choice[0] for choice in UserTimerPreference.WEIGHT_UNIT_CHOICES]
        if preferred_weight_unit not in valid_units:
            errors.append('Invalid weight unit selection.')

        # Validate timer fields
        try:
            primary_timer_int = int(primary_timer_seconds)
            if not (10 <= primary_timer_int <= 3600):
                errors.append('Primary timer must be between 10 and 3600 seconds.')
        except (ValueError, TypeError):
            errors.append('Primary timer must be a valid integer.')

        try:
            secondary_timer_int = int(secondary_timer_seconds)
            if not (10 <= secondary_timer_int <= 3600):
                errors.append('Secondary timer must be between 10 and 3600 seconds.')
        except (ValueError, TypeError):
            errors.append('Secondary timer must be a valid integer.')

        try:
            accessory_timer_int = int(accessory_timer_seconds)
            if not (10 <= accessory_timer_int <= 3600):
                errors.append('Accessory timer must be between 10 and 3600 seconds.')
        except (ValueError, TypeError):
            errors.append('Accessory timer must be a valid integer.')

        # Validate auto-progression fields
        try:
            default_weight_increment_decimal = Decimal(default_weight_increment)
            if default_weight_increment_decimal < 0:
                errors.append('Weight increment must be positive.')
        except (ValueError, TypeError):
            errors.append('Weight increment must be a valid number.')

        try:
            default_rep_increment_int = int(default_rep_increment)
            if default_rep_increment_int < 1:
                errors.append('Rep increment must be at least 1.')
        except (ValueError, TypeError):
            errors.append('Rep increment must be a valid integer.')

        if not errors:
            try:
                # Update user basic info
                user.username = new_username
                user.email = new_email
                user.save()

                # Update timer preferences (all fields)
                timer_prefs.preferred_weight_unit = preferred_weight_unit
                timer_prefs.primary_timer_seconds = int(primary_timer_seconds)
                timer_prefs.secondary_timer_seconds = int(secondary_timer_seconds)
                timer_prefs.accessory_timer_seconds = int(accessory_timer_seconds)
                timer_prefs.auto_start_timer = auto_start_timer
                timer_prefs.timer_sound_enabled = timer_sound_enabled
                timer_prefs.auto_progression_enabled = auto_progression_enabled
                timer_prefs.default_weight_increment = Decimal(default_weight_increment)
                timer_prefs.default_rep_increment = int(default_rep_increment)
                timer_prefs.save()

                messages.success(request, 'Profile and timer settings updated successfully!')
                return redirect('profile')
            except Exception as e:
                errors.append(f'Error updating profile: {str(e)}')

        context = {
            'title': 'My Profile',
            'user': user,
            'timer_prefs': timer_prefs,
            'weight_unit_choices': UserTimerPreference.WEIGHT_UNIT_CHOICES,
            'errors': errors,
        }
        return render(request, 'profile.html', context)

    # GET request
    context = {
        'title': 'My Profile',
        'user': user,
        'timer_prefs': timer_prefs,
        'weight_unit_choices': UserTimerPreference.WEIGHT_UNIT_CHOICES,
    }
    return render(request, 'profile.html', context)

# ============================================================================
# EXERCISE TIMER OVERRIDE API ENDPOINTS
# ============================================================================

@login_required
def api_exercise_timer_overrides(request):
    """API endpoint to manage exercise timer overrides (GET/POST)"""
    if request.method == 'GET':
        try:
            # Get all timer overrides for the current user
            overrides = ExerciseTimerOverride.objects.filter(
                user=request.user
            ).select_related('exercise').order_by('exercise__name')

            override_data = []
            for override in overrides:
                override_data.append({
                    'id': override.id,
                    'exercise_id': override.exercise.id,
                    'exercise_name': override.exercise.name,
                    'exercise_category': override.exercise.category.name if override.exercise.category else None,
                    'timer_seconds': override.timer_seconds,
                })

            return JsonResponse({
                'overrides': override_data
            })

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    elif request.method == 'POST':
        try:
            # Parse JSON data from request body
            data = json.loads(request.body.decode('utf-8'))

            exercise_id = data.get('exercise_id')
            timer_seconds = data.get('timer_seconds')

            # Validate required fields
            errors = {}

            if not exercise_id:
                errors['exercise_id'] = ['Exercise is required.']

            if not timer_seconds:
                errors['timer_seconds'] = ['Timer duration is required.']
            else:
                try:
                    timer_seconds_int = int(timer_seconds)
                    if timer_seconds_int < 10:
                        errors['timer_seconds'] = ['Timer duration must be at least 10 seconds.']
                    elif timer_seconds_int > 3600:
                        errors['timer_seconds'] = ['Timer duration must be no more than 3600 seconds (1 hour).']
                except (ValueError, TypeError):
                    errors['timer_seconds'] = ['Timer duration must be a valid number.']

            if errors:
                return JsonResponse({'errors': errors}, status=400)

            # Validate exercise exists and user has access
            try:
                exercise = Exercise.objects.get(
                    Q(id=exercise_id) &
                    (Q(is_custom=False) | Q(created_by=request.user))
                )
            except Exercise.DoesNotExist:
                return JsonResponse({'errors': {'exercise_id': ['Exercise not found.']}}, status=400)

            # Create or update the timer override
            override, created = ExerciseTimerOverride.objects.update_or_create(
                user=request.user,
                exercise=exercise,
                defaults={'timer_seconds': timer_seconds_int}
            )

            return JsonResponse({
                'success': True,
                'created': created,
                'override': {
                    'id': override.id,
                    'exercise_id': override.exercise.id,
                    'exercise_name': override.exercise.name,
                    'exercise_category': override.exercise.category.name if override.exercise.category else None,
                    'timer_seconds': override.timer_seconds,
                }
            })

        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON data.'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'error': 'Method not allowed.'}, status=405)

@login_required
def api_exercise_timer_override_delete(request, override_id):
    """API endpoint to delete a specific exercise timer override (DELETE)"""
    if request.method == 'DELETE':
        try:
            override = get_object_or_404(
                ExerciseTimerOverride,
                id=override_id,
                user=request.user
            )

            override_data = {
                'id': override.id,
                'exercise_name': override.exercise.name,
                'timer_seconds': override.timer_seconds,
            }

            override.delete()

            return JsonResponse({
                'success': True,
                'deleted_override': override_data
            })

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'error': 'Method not allowed.'}, status=405)

@login_required
def api_exercises_search(request):
    """API endpoint to search exercises for dropdown selection"""
    if request.method == 'GET':
        try:
            search_query = request.GET.get('q', '').strip()
            limit = min(int(request.GET.get('limit', 50)), 100)  # Max 100 results

            # Build queryset - user can access built-in exercises and their custom ones
            exercises = Exercise.objects.filter(
                Q(is_custom=False) | Q(created_by=request.user)
            )

            # Apply search filter if provided
            if search_query:
                exercises = exercises.filter(
                    Q(name__icontains=search_query) |
                    Q(category__name__icontains=search_query)
                ).distinct()

            # Order by name and limit results
            exercises = exercises.select_related('category').order_by('name')[:limit]

            exercise_data = []
            for exercise in exercises:
                exercise_data.append({
                    'id': exercise.id,
                    'name': exercise.name,
                    'category': exercise.category.name if exercise.category else 'Uncategorized',
                    'exercise_type': exercise.exercise_type,
                })

            return JsonResponse({
                'exercises': exercise_data,
                'total': len(exercise_data)
            })

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'error': 'Method not allowed.'}, status=405)

# ============================================================================
# PROGRAM AND ROUTINE TIMER PREFERENCES API ENDPOINTS
# ============================================================================

@login_required
def api_program_timer_preferences(request, program_id):
    """API endpoint to manage program timer preferences (GET/POST)"""
    # Verify user owns the program
    program = get_object_or_404(Program, id=program_id, user=request.user)

    if request.method == 'GET':
        try:
            # Get program timer preferences if they exist
            prefs = getattr(program, 'timer_preferences', None)

            if prefs:
                return JsonResponse({
                    'primary_timer_seconds': prefs.primary_timer_seconds,
                    'secondary_timer_seconds': prefs.secondary_timer_seconds,
                    'accessory_timer_seconds': prefs.accessory_timer_seconds,
                    'auto_start_timer': prefs.auto_start_timer,
                })
            else:
                # Return null values if no preferences set
                return JsonResponse({
                    'primary_timer_seconds': None,
                    'secondary_timer_seconds': None,
                    'accessory_timer_seconds': None,
                    'auto_start_timer': None,
                })

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    elif request.method == 'POST':
        try:
            data = json.loads(request.body.decode('utf-8'))

            # Get or create program timer preferences
            prefs, created = ProgramTimerPreference.objects.get_or_create(program=program)

            # Update fields if provided
            if 'primary_timer_seconds' in data:
                prefs.primary_timer_seconds = data['primary_timer_seconds'] if data['primary_timer_seconds'] else None
            if 'secondary_timer_seconds' in data:
                prefs.secondary_timer_seconds = data['secondary_timer_seconds'] if data['secondary_timer_seconds'] else None
            if 'accessory_timer_seconds' in data:
                prefs.accessory_timer_seconds = data['accessory_timer_seconds'] if data['accessory_timer_seconds'] else None
            if 'auto_start_timer' in data:
                prefs.auto_start_timer = data['auto_start_timer'] if data['auto_start_timer'] is not None else None

            prefs.save()

            return JsonResponse({
                'success': True,
                'primary_timer_seconds': prefs.primary_timer_seconds,
                'secondary_timer_seconds': prefs.secondary_timer_seconds,
                'accessory_timer_seconds': prefs.accessory_timer_seconds,
                'auto_start_timer': prefs.auto_start_timer,
            })

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'error': 'Method not allowed.'}, status=405)

@login_required
def api_routine_timer_preferences(request, routine_id):
    """API endpoint to manage routine timer preferences (GET/POST)"""
    # Verify user owns the routine
    routine = get_object_or_404(Routine, id=routine_id, user=request.user)

    if request.method == 'GET':
        try:
            # Get routine timer preferences if they exist
            prefs = getattr(routine, 'timer_preferences', None)

            if prefs:
                return JsonResponse({
                    'primary_timer_seconds': prefs.primary_timer_seconds,
                    'secondary_timer_seconds': prefs.secondary_timer_seconds,
                    'accessory_timer_seconds': prefs.accessory_timer_seconds,
                    'auto_start_timer': prefs.auto_start_timer,
                })
            else:
                # Return null values if no preferences set
                return JsonResponse({
                    'primary_timer_seconds': None,
                    'secondary_timer_seconds': None,
                    'accessory_timer_seconds': None,
                    'auto_start_timer': None,
                })

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    elif request.method == 'POST':
        try:
            data = json.loads(request.body.decode('utf-8'))

            # Get or create routine timer preferences
            prefs, created = RoutineTimerPreference.objects.get_or_create(routine=routine)

            # Update fields if provided
            if 'primary_timer_seconds' in data:
                prefs.primary_timer_seconds = data['primary_timer_seconds'] if data['primary_timer_seconds'] else None
            if 'secondary_timer_seconds' in data:
                prefs.secondary_timer_seconds = data['secondary_timer_seconds'] if data['secondary_timer_seconds'] else None
            if 'accessory_timer_seconds' in data:
                prefs.accessory_timer_seconds = data['accessory_timer_seconds'] if data['accessory_timer_seconds'] else None
            if 'auto_start_timer' in data:
                prefs.auto_start_timer = data['auto_start_timer'] is not None and data['auto_start_timer']

            prefs.save()

            return JsonResponse({
                'success': True,
                'primary_timer_seconds': prefs.primary_timer_seconds,
                'secondary_timer_seconds': prefs.secondary_timer_seconds,
                'accessory_timer_seconds': prefs.accessory_timer_seconds,
                'auto_start_timer': prefs.auto_start_timer,
            })

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'error': 'Method not allowed.'}, status=405)


def normalize_rep_range(rep_range, min_reps=None, max_reps=None):
    """Return sanitized rep range selector and optional min/max bounds."""

    valid_ranges = {'', 'low', 'mid', 'high', 'custom'}
    normalized = (rep_range or '').strip().lower()
    if normalized not in valid_ranges:
        normalized = ''

    min_value = max_value = None
    if normalized == 'custom':
        try:
            min_value = int(min_reps)
        except (TypeError, ValueError):
            min_value = 1
        try:
            max_value = int(max_reps)
        except (TypeError, ValueError):
            max_value = min_value

        min_value = max(1, min_value)
        min_value = min(30, min_value)
        max_value = max(1, max_value)
        max_value = min(30, max_value)
        if max_value < min_value:
            max_value = min_value

    return normalized, min_value, max_value


def aggregate_exercise_sets_for_chart(sets, chart_type='1rm', comparison_type='average'):
    """Aggregate exercise sets to a single data point per workout."""
    chart_type = (chart_type or '1rm').lower()
    comparison_type = (comparison_type or 'average').lower()

    workouts = defaultdict(lambda: {
        'date': None,
        'estimates': [],
        'weights': [],
        'volumes': [],
    })

    for set_obj in sets:
        if getattr(set_obj, 'is_warmup', False):
            continue

        if set_obj.weight is None or set_obj.reps is None:
            continue

        workout = set_obj.workout_exercise.workout
        entry = workouts[workout.id]
        if entry['date'] is None:
            entry['date'] = workout.date

        volume_value = float(set_obj.get_volume())
        entry['volumes'].append(volume_value)
        entry['weights'].append(float(set_obj.weight))

        if set_obj.is_valid_for_1rm():
            estimate = set_obj.get_best_1rm_estimate()
            if estimate is not None:
                entry['estimates'].append(float(estimate))

    points = []
    for workout_id, entry in sorted(
        workouts.items(),
        key=lambda item: item[1]['date'] or timezone.now(),
    ):
        estimates = entry['estimates']
        weights = entry['weights']
        volumes = entry['volumes']

        if comparison_type in ('peak', 'heaviest'):
            estimate_value = max(estimates) if estimates else None
            weight_value = max(weights) if weights else None
        else:
            estimate_value = statistics.mean(estimates) if estimates else None
            weight_value = statistics.mean(weights) if weights else None

        volume_total = sum(volumes) if volumes else 0
        y_value = volume_total if chart_type == 'volume' else estimate_value
        iso_date = (entry['date'] or timezone.now()).isoformat()
        points.append({
            'x': iso_date,
            'date': iso_date,
            'y': float(y_value) if y_value is not None else None,
            'estimated_1rm': float(estimate_value) if estimate_value is not None else None,
            'weight': float(weight_value) if weight_value is not None else None,
            'volume': float(volume_total),
            'workout_id': workout_id,
        })

    return points

@login_required
def progress_overview(request):
    """Dashboard showing exercise progress trends and statistics"""

    # Get filtering parameters
    period_days = int(request.GET.get('period', '30'))
    selected_rep_range = request.GET.get('rep_range', '')
    selected_chart_type = request.GET.get('chart_type', '1rm')
    custom_min_reps = request.GET.get('min_reps', '')
    custom_max_reps = request.GET.get('max_reps', '')

    metrics = get_progress_metrics(request.user, period_days)
    top_exercises = get_top_exercises_by_volume(
        request.user,
        period_days,
        limit=6,
        with_volume=True,
    )

    exercise_options = list(
        Exercise.objects.filter(
            workoutexercise__workout__user=request.user,
            workoutexercise__sets__isnull=False
        )
        .distinct()
        .order_by('name')
        .values('id', 'name')
    )

    selected_exercise_id = request.GET.get('exercise', '')

    context = {
        'metrics': metrics,
        'top_exercises': top_exercises,
        'exercise_options': exercise_options,
        'period_days': period_days,
        'selected_exercise_id': selected_exercise_id,
        'selected_rep_range': selected_rep_range,
        'selected_chart_type': selected_chart_type,
        'custom_min_reps': custom_min_reps,
        'custom_max_reps': custom_max_reps,
        'title': 'Progress Overview'
    }

    return render(request, 'progress/overview.html', context)


@login_required
def exercise_progress_detail(request, exercise_id):
    """Detailed progress view for a specific exercise"""

    exercise = get_object_or_404(Exercise, id=exercise_id)

    # Verify user can access this exercise
    if exercise.is_custom and exercise.user != request.user:
        raise Http404("Exercise not found")

    # Get filtering parameters
    try:
        period_days = max(1, int(request.GET.get('period', '90')))
    except (TypeError, ValueError):
        period_days = 90

    raw_rep_range = request.GET.get('rep_range', '')
    rep_range, min_reps_value, max_reps_value = normalize_rep_range(
        raw_rep_range,
        request.GET.get('min_reps'),
        request.GET.get('max_reps'),
    )

    comparison_type = (request.GET.get('comparison', 'average') or 'average').lower()
    if comparison_type == 'heaviest':
        comparison_type = 'peak'
    if comparison_type not in ('average', 'peak'):
        comparison_type = 'average'

    chart_type = (request.GET.get('chart_type', '1rm') or '1rm').lower()
    if chart_type not in ('1rm', 'volume'):
        chart_type = '1rm'

    custom_min_reps = str(min_reps_value) if min_reps_value is not None else ''
    custom_max_reps = str(max_reps_value) if max_reps_value is not None else ''

    # Get exercise sets with filtering
    sets_query = ExerciseSet.objects.filter(
        workout_exercise__workout__user=request.user,
        workout_exercise__exercise=exercise,
        workout_exercise__workout__date__gte=timezone.now() - timedelta(days=period_days)
    ).select_related('workout_exercise__workout')

    # Apply rep range filtering
    if rep_range == 'low':
        sets_query = sets_query.filter(reps__range=(1, 3))
    elif rep_range == 'mid':
        sets_query = sets_query.filter(reps__range=(4, 6))
    elif rep_range == 'high':
        sets_query = sets_query.filter(reps__gte=7)
    elif rep_range == 'custom' and min_reps_value is not None and max_reps_value is not None:
        sets_query = sets_query.filter(reps__range=(min_reps_value, max_reps_value))

    ordered_sets = list(sets_query.order_by('workout_exercise__workout__date', 'set_number'))

    # Build chart data
    progress_data = get_exercise_progress(request.user, exercise, period_days)
    chart_data = aggregate_exercise_sets_for_chart(ordered_sets, chart_type, comparison_type)

    non_warmup_sets = [
        s for s in ordered_sets
        if not getattr(s, 'is_warmup', False)
    ]
    recent_sets = []
    for set_obj in sorted(
        non_warmup_sets,
        key=lambda s: (
            s.workout_exercise.workout.date,
            s.workout_exercise.workout.id,
            getattr(s, 'set_number', 0),
        ),
        reverse=True,
    )[:10]:
        estimated_1rm = set_obj.get_best_1rm_estimate() if set_obj.is_valid_for_1rm() else None
        recent_sets.append({
            'date': set_obj.workout_exercise.workout.date,
            'weight': set_obj.weight,
            'reps': set_obj.reps,
            'estimated_1rm': estimated_1rm,
        })

    context = {
        'exercise': exercise,
        'chart_data': chart_data,
        'progress_data': progress_data,
        'recent_sets': recent_sets,
        'period_days': period_days,
        'rep_range': rep_range,
        'comparison_type': comparison_type,
        'chart_type': chart_type,
        'custom_min_reps': custom_min_reps,
        'custom_max_reps': custom_max_reps,
        'title': f'{exercise.name} Progress'
    }

    return render(request, 'progress/exercise_detail.html', context)


@login_required
def api_exercise_chart_data(request, exercise_id):
    """API endpoint for exercise chart data with filtering"""

    if request.method != 'GET':
        return JsonResponse({'error': 'Only GET allowed'}, status=405)

    try:
        exercise = get_object_or_404(Exercise, id=exercise_id)

        # Verify access
        if exercise.is_custom and exercise.user != request.user:
            return JsonResponse({'error': 'Access denied'}, status=403)

        # Get parameters
        try:
            period_days = max(1, int(request.GET.get('period', '90')))
        except (TypeError, ValueError):
            period_days = 90

        rep_range, min_reps_value, max_reps_value = normalize_rep_range(
            request.GET.get('rep_range', ''),
            request.GET.get('min_reps'),
            request.GET.get('max_reps'),
        )

        comparison_type = (request.GET.get('comparison', 'average') or 'average').lower()
        if comparison_type == 'heaviest':
            comparison_type = 'peak'
        if comparison_type not in ('average', 'peak'):
            comparison_type = 'average'

        chart_type = (request.GET.get('chart_type', '1rm') or '1rm').lower()
        if chart_type not in ('1rm', 'volume'):
            chart_type = '1rm'

        # Query sets with filtering
        sets_query = ExerciseSet.objects.filter(
            workout_exercise__workout__user=request.user,
            workout_exercise__exercise=exercise,
            workout_exercise__workout__date__gte=timezone.now() - timedelta(days=period_days)
        ).select_related('workout_exercise__workout')

        # Apply rep range filter
        if rep_range == 'low':
            sets_query = sets_query.filter(reps__range=(1, 3))
        elif rep_range == 'mid':
            sets_query = sets_query.filter(reps__range=(4, 6))
        elif rep_range == 'high':
            sets_query = sets_query.filter(reps__gte=7)
        elif rep_range == 'custom':
            if min_reps_value is not None and max_reps_value is not None:
                sets_query = sets_query.filter(reps__range=(min_reps_value, max_reps_value))

        ordered_sets = list(sets_query.order_by('workout_exercise__workout__date', 'set_number'))
        chart_data = aggregate_exercise_sets_for_chart(ordered_sets, chart_type, comparison_type)

        return JsonResponse({
            'success': True,
            'data': chart_data,
            'exercise_name': exercise.name,
            'chart_type': chart_type,
            'period_days': period_days,
            'rep_range': rep_range,
            'comparison_type': comparison_type,
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def api_progress_filter_options(request):
    """Get available filtering options for progress views"""

    try:
        # Get user's exercises with recorded sets
        exercises_with_data = Exercise.objects.filter(
            workoutexercise__workout__user=request.user,
            workoutexercise__sets__isnull=False
        ).distinct().order_by('name')

        exercise_options = [
            {'id': ex.id, 'name': ex.name, 'type': ex.exercise_type}
            for ex in exercises_with_data
        ]

        # Get date ranges with data
        oldest_workout = Workout.objects.filter(user=request.user).aggregate(
            Min('date')
        )['date__min']

        date_ranges = [
            {'value': 7, 'label': '1 Week'},
            {'value': 30, 'label': '1 Month'},
            {'value': 90, 'label': '3 Months'},
            {'value': 180, 'label': '6 Months'},
            {'value': 365, 'label': '1 Year'},
        ]

        if oldest_workout:
            days_since_oldest = (timezone.now().date() - oldest_workout.date()).days
            date_ranges.append({'value': days_since_oldest, 'label': 'All Time'})

        return JsonResponse({
            'exercises': exercise_options,
            'date_ranges': date_ranges,
            'rep_ranges': [
                {'value': '', 'label': 'All Rep Ranges'},
                {'value': 'low', 'label': 'Low Reps (1-3)'},
                {'value': 'mid', 'label': 'Mid Reps (4-6)'},
                {'value': 'high', 'label': 'High Reps (7+)'},
                {'value': 'custom', 'label': 'Custom Range'},
            ]
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def progress_pr_history(request):
    period_days = int(request.GET.get('period', '365'))
    exercise_id = request.GET.get('exercise')
    exercise = None
    if exercise_id:
        exercise = get_object_or_404(Exercise, id=exercise_id)
        if exercise.is_custom and exercise.user != request.user:
            raise Http404('Exercise not found')

    summary = get_personal_records_summary(request.user, period_days)
    records = get_personal_records(request.user, period_days, exercise)[:50]

    context = {
        'summary': summary,
        'records': records,
        'selected_period': period_days,
        'selected_exercise': exercise,
        'exercises': Exercise.objects.filter(workoutexercise__workout__user=request.user).distinct().order_by('name'),
        'title': 'Personal Records'
    }
    return render(request, 'progress/pr_history.html', context)

def service_worker(request):
    """Serve the service worker JavaScript for background timer notifications.

    Served at '/service-worker.js' so the worker can control the root scope.
    Uses staticfiles finders so this works in development without collectstatic.
    """
    # Try to locate the file via staticfiles finders (works in DEBUG without collectstatic)
    path = finders.find('service-worker.js')
    if not path:
        # Fallback to storage (e.g., after collectstatic)
        try:
            file_handle = staticfiles_storage.open('service-worker.js', mode='rb')
        except FileNotFoundError:
            raise Http404('Service worker file not found.')
    else:
        file_handle = open(path, 'rb')

    response = FileResponse(file_handle, content_type='application/javascript')
    response['Cache-Control'] = 'no-cache'
    response['Service-Worker-Allowed'] = '/'
    return response

