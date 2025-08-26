from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db import models, transaction
from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from gainz.exercises.models import Exercise, ExerciseCategory
from gainz.exercises.serializers import ExerciseSerializer, ExerciseCategorySerializer
from gainz.workouts.models import Workout, WorkoutExercise, ExerciseSet, Program, Routine, RoutineExercise, RoutineExerciseSet, ProgramRoutine
from gainz.workouts.serializers import WorkoutSerializer, WorkoutExerciseSerializer, ExerciseSetSerializer
from django.http import JsonResponse, HttpResponse, HttpResponseBadRequest, HttpResponseForbidden, Http404
from django.template.loader import render_to_string
from django.db.models import Q
import datetime # Add datetime import
from gainz.workouts.utils import get_prefill_data # Add get_prefill_data import
from django.utils import timezone # Added for timezone.now()
from django.urls import reverse # Add import for reverse
from django.contrib import messages # Added for messages
from django.core.cache import cache # Added for Redis cache
import json # Moved import json here

# Make Redis optional for deployments without Redis
def get_redis_connection():
    try:
        from django_rq import get_queue
        return get_queue().connection
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

    # Fetch WorkoutExercises related to this workout, prefetching related Exercise and Sets
    workout_exercises = workout.exercises.prefetch_related('exercise', 'sets').all()

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

    context = {
        'workout': workout,
        'primary_exercises': primary_exercises,
        'secondary_exercises': secondary_exercises,
        'accessory_exercises': accessory_exercises,
        'title': f"Workout: {workout.name}" # Added a title for the page
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
    """Display a list of exercises organized by category and provide data for the add modal."""

    search_query = request.GET.get('search_query', '')
    exercise_type_filter = request.GET.get('exercise_type', '')
    category_filter = request.GET.get('category', '')

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
    """Display a list of the user's programs and routines."""
    # Fetch programs with their routines prefetched
    programs = Program.objects.filter(user=request.user).prefetch_related('routines').order_by('name')

    # Fetch standalone routines (those not assigned to any program)
    routines = Routine.objects.filter(user=request.user).order_by('name')

    context = {
        'programs': programs,
        'routines': routines,
        'title': 'My Routines & Programs'
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
            program.name = request.POST.get('name', program.name)
            program.description = request.POST.get('description', program.description)
            program.is_active = request.POST.get('is_active') == 'on'
            program.scheduling_type = request.POST.get('scheduling_type', 'weekly')
            program.save()

            # Clear existing routines for this program
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
def start_workout_from_routine(request, routine_id):
    routine = get_object_or_404(Routine, id=routine_id, user=request.user)
    routine_exercises_with_sets = []
    today = datetime.date.today()
    prefilled_workout_name = None

    if request.method == 'GET' and request.GET.get('source') == 'smart-start':
        # Auto-generate workout name: "Routine Name #X"
        completed_count = Workout.objects.filter(user=request.user, routine_source=routine).count()
        prefilled_workout_name = f"{routine.name} #{completed_count + 1}"

    for re in routine.exercises.prefetch_related('planned_sets', 'exercise').order_by('order'):
        sets_data = []
        for set_template in re.planned_sets.all().order_by('set_number'):
            prefill = get_prefill_data(request.user, set_template, today)
            sets_data.append({
                'template': set_template,
                'prefill_reps': prefill.get('reps'),
                'prefill_weight': prefill.get('weight'),
            })
        routine_exercises_with_sets.append({
            'routine_exercise': re,
            'exercise': re.exercise,
            'sets': sets_data
        })

    if request.method == 'POST':
        try:
            with transaction.atomic():
                workout_name = request.POST.get('workout_name', routine.name) # Default to routine name if not provided
                workout_notes = request.POST.get('workout_notes', '')

                # Create the Workout instance
                new_workout = Workout.objects.create(
                    user=request.user,
                    name=workout_name,
                    notes=workout_notes,
                    date=datetime.datetime.now(), # Use current datetime
                    routine_source=routine
                )

                # Process each exercise and its sets
                exercise_idx = 0
                while True:
                    # Check if the routine_exercise_id for the current index exists in POST
                    # This also implicitly checks if there are more exercises to process based on form naming
                    routine_exercise_id_key = f'routine_exercise_id_{exercise_idx}'
                    if routine_exercise_id_key not in request.POST:
                        break # No more exercises submitted

                    routine_exercise_id = request.POST.get(routine_exercise_id_key)
                    exercise_notes = request.POST.get(f'exercise_notes_{exercise_idx}', '')

                    try:
                        source_routine_exercise = RoutineExercise.objects.get(id=routine_exercise_id, routine=routine)
                    except RoutineExercise.DoesNotExist:
                        # This should ideally not happen if form is generated correctly
                        # but good to handle. Maybe log an error or skip.
                        exercise_idx += 1
                        continue

                    # Create WorkoutExercise
                    workout_exercise_instance = WorkoutExercise.objects.create(
                        workout=new_workout,
                        exercise=source_routine_exercise.exercise,
                        order=source_routine_exercise.order, # Use order from RoutineExercise
                        notes=exercise_notes,
                        routine_exercise_source=source_routine_exercise,
                        exercise_type=source_routine_exercise.routine_specific_exercise_type or source_routine_exercise.exercise.exercise_type
                    )

                    # Process sets for this WorkoutExercise
                    set_idx = 0
                    while True:
                        # Check for presence of a set field for this exercise_idx and set_idx
                        # Using set_template_id as a key, assuming every submitted set will have it
                        set_template_id_key = f'set_template_id_{exercise_idx}_{set_idx}'
                        if set_template_id_key not in request.POST:
                            break # No more sets for this exercise

                        # We don't strictly need set_template_id for creating ExerciseSet,
                        # but it confirms the set was part of the form submission for this loop.
                        # set_template_id = request.POST.get(set_template_id_key)

                        reps_str = request.POST.get(f'reps_{exercise_idx}_{set_idx}')
                        weight_str = request.POST.get(f'weight_{exercise_idx}_{set_idx}')
                        is_warmup = request.POST.get(f'is_warmup_{exercise_idx}_{set_idx}') == 'true'

                        # Only save the set if reps and weight are provided
                        if reps_str and weight_str:
                            try:
                                reps = int(reps_str)
                                weight = float(weight_str)

                                # Get the set number from the original template if possible, or just increment
                                # For simplicity, we'll use the set_idx + 1 as set_number for the logged set.
                                # The original template set_number is available via set_data.template.set_number in GET
                                # but for POST, we need to be careful. We assume the order is maintained.
                                # A more robust way would be to pass set_template.set_number in a hidden field for each set.
                                # For now, using sequential set_number for logged sets.

                                ExerciseSet.objects.create(
                                    workout_exercise=workout_exercise_instance,
                                    set_number=set_idx + 1, # Simple sequential set number for logged sets
                                    reps=reps,
                                    weight=weight,
                                    is_warmup=is_warmup
                                )
                            except (ValueError, TypeError):
                                # Invalid number for reps/weight, skip this set or log error
                                pass # Silently skip malformed set data for now
                        set_idx += 1
                    exercise_idx += 1

                return redirect('workout-detail', workout_id=new_workout.id)
        except Exception as e:
            # Log the error e
            # Add a message to Django messages framework or pass error to context
            # For now, re-rendering the form with a generic error might be complex
            # as we need to reconstruct routine_exercises_with_sets with submitted data
            # A simple redirect or a dedicated error page might be better initially.
            # Or, for a more user-friendly approach, one would repopulate the form.
            # For now, just printing error and re-rendering the initial GET version of the page.
            print(f"Error processing start_workout_from_routine POST: {e}")
            # This will lose user's input on error, which is not ideal.
            # Consider adding Django messages framework for error feedback.

    # GET request or if POST fails and we fall through (not ideal error handling yet)
    context = {
        'routine': routine,
        'routine_exercises_with_sets': routine_exercises_with_sets,
        'title': f'Start Workout: {routine.name}',
        'prefilled_workout_name': prefilled_workout_name
    }
    return render(request, 'start_workout_from_routine.html', context)

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
        # Optionally, add a success message using Django's messages framework
        return redirect('workout-list')

    context = {
        'object': workout, # Using 'object' for consistency with other delete views
        'title': f'Delete Workout: {workout.name}'
    }
    return render(request, 'workout_confirm_delete.html', context)

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

        else: # Sequential schedule logic
            last_workout = Workout.objects.filter(
                user=user,
                routine_source__program_associations__program=active_program
            ).order_by('-date').first()

            next_order = 1
            if last_workout and last_workout.routine_source:
                last_program_routine = ProgramRoutine.objects.filter(
                    program=active_program,
                    routine=last_workout.routine_source
                ).first()
                if last_program_routine:
                    next_order = last_program_routine.order + 1

            next_program_routine = ProgramRoutine.objects.filter(
                program=active_program,
                order__gte=next_order
            ).order_by('order').select_related('routine').first()

            if not next_program_routine:  # Wrap around to the start
                next_program_routine = ProgramRoutine.objects.filter(
                    program=active_program
                ).order_by('order').select_related('routine').first()

            if next_program_routine:
                next_routine = next_program_routine.routine

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

# Health check view for Railway deployment
def health_check(request):
    """Simple health check endpoint for Railway"""
    return HttpResponse("OK", content_type="text/plain")