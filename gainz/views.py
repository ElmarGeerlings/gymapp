from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db import models
from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from gainz.exercises.models import Exercise, ExerciseCategory
from gainz.exercises.serializers import ExerciseSerializer, ExerciseCategorySerializer
from gainz.workouts.models import Workout, WorkoutExercise, ExerciseSet, Program, Routine, RoutineExercise
from gainz.workouts.serializers import WorkoutSerializer, WorkoutExerciseSerializer, ExerciseSetSerializer
from django.http import JsonResponse, HttpResponse
from django.template.loader import render_to_string
from django.db.models import Q

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
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description', '')

        # Basic validation (more can be added)
        if not name:
            all_exercises = Exercise.objects.filter(Q(is_custom=False) | Q(is_custom=True, user=request.user)).order_by('name')
            return render(request, 'routine_form.html', {
                'title': 'Create New Routine',
                'error': 'Name is required.',
                'all_exercises': all_exercises,
                'name_value': name,
                'description_value': description,
            })

        routine = Routine.objects.create(
            user=request.user,
            name=name,
            description=description,
        )

        # Process RoutineExercise data
        form_count = int(request.POST.get('routine_exercise_form_count', 0))
        for i in range(form_count):
            exercise_pk = request.POST.get(f'exercise_pk_{i}')
            order = request.POST.get(f'order_{i}', 0)
            target_sets = request.POST.get(f'target_sets_{i}')
            target_reps = request.POST.get(f'target_reps_{i}', '')
            target_rest_seconds = request.POST.get(f'target_rest_seconds_{i}')

            if not exercise_pk or not target_sets or not target_reps: # Basic validation
                # Optionally add more robust error handling here,
                # e.g. re-render form with errors and submitted data
                continue # Skip this invalid exercise entry

            try:
                exercise_instance = Exercise.objects.get(pk=exercise_pk)

                RoutineExercise.objects.create(
                    routine=routine,
                    exercise=exercise_instance,
                    order=int(order),
                    target_sets=int(target_sets),
                    target_reps=target_reps,
                    target_rest_seconds=int(target_rest_seconds) if target_rest_seconds else None,
                )
            except Exercise.DoesNotExist:
                # Handle error: selected exercise does not exist
                continue # Skip
            except ValueError: # For int conversion errors
                # Handle error: invalid number format
                continue # Skip

        return redirect('routine-detail', routine_id=routine.id)
    else:
        # Generate default routine name
        last_routine_number = Routine.objects.filter(user=request.user).count()
        default_routine_name = f"Routine {last_routine_number + 1}"
        all_exercises = Exercise.objects.filter(Q(is_custom=False) | Q(is_custom=True, user=request.user)).order_by('name')
    return render(request, 'routine_form.html', {
        'title': 'Create New Routine',
        'all_exercises': all_exercises,
        'name_value': default_routine_name, # Pass default name
    })

@login_required
def routine_update(request, routine_id):
    routine = get_object_or_404(Routine, id=routine_id, user=request.user)
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description', '')

        if not name:
            all_exercises = Exercise.objects.filter(Q(is_custom=False) | Q(is_custom=True, user=request.user)).order_by('name')
            # Fetch existing routine exercises for re-rendering form with errors
            existing_routine_exercises = routine.exercises.select_related('exercise').order_by('order')
            return render(request, 'routine_form.html', {
                'form': None,
                'title': f'Edit Routine: {routine.name}',
                'object': routine,
                'error': 'Name is required.',
                'all_exercises': all_exercises,
                'routine_exercises': existing_routine_exercises, # Pass existing for error re-render
                'name_value': name,
                'description_value': description,
            })

        routine.name = name
        routine.description = description

        routine.save()

        # Process RoutineExercise data
        submitted_ids = set() # Keep track of IDs of submitted existing exercises
        form_count = int(request.POST.get('routine_exercise_form_count', 0))

        for i in range(form_count):
            exercise_pk = request.POST.get(f'exercise_pk_{i}')
            order = request.POST.get(f'order_{i}', 0)
            target_sets = request.POST.get(f'target_sets_{i}')
            target_reps = request.POST.get(f'target_reps_{i}', '')
            target_rest_seconds = request.POST.get(f'target_rest_seconds_{i}')
            routine_exercise_id = request.POST.get(f'routine_exercise_id_{i}')

            if not exercise_pk or not target_sets or not target_reps: # Basic validation
                continue

            try:
                exercise_instance = Exercise.objects.get(pk=exercise_pk)

                if routine_exercise_id: # Existing exercise
                    re_instance = RoutineExercise.objects.get(id=routine_exercise_id, routine=routine)
                    re_instance.exercise = exercise_instance
                    re_instance.order = int(order)
                    re_instance.target_sets = int(target_sets)
                    re_instance.target_reps = target_reps
                    re_instance.target_rest_seconds = int(target_rest_seconds) if target_rest_seconds else None
                    re_instance.save()
                    submitted_ids.add(re_instance.id)
                else: # New exercise
                    new_re = RoutineExercise.objects.create(
                        routine=routine,
                        exercise=exercise_instance,
                        order=int(order),
                        target_sets=int(target_sets),
                        target_reps=target_reps,
                        target_rest_seconds=int(target_rest_seconds) if target_rest_seconds else None,
                    )
                    submitted_ids.add(new_re.id) # Though it's new, adding to submitted_ids is harmless here
            except Exercise.DoesNotExist:
                continue
            except RoutineExercise.DoesNotExist: # If an ID was spoofed or belongs to another routine
                continue
            except ValueError:
                continue

        # Delete RoutineExercises that were not in the submission
        # This assumes that if an existing exercise is not submitted, it should be deleted.
        # If an exercise was merely cleared of its values, it might still be submitted with an ID but empty required fields (handled by basic validation above).
        existing_exercise_ids = set(routine.exercises.values_list('id', flat=True))
        ids_to_delete = existing_exercise_ids - submitted_ids
        if ids_to_delete:
            RoutineExercise.objects.filter(id__in=ids_to_delete, routine=routine).delete()

        return redirect('routine-detail', routine_id=routine.id)
    else:
        all_exercises = Exercise.objects.filter(Q(is_custom=False) | Q(is_custom=True, user=request.user)).order_by('name')
        existing_routine_exercises = routine.exercises.select_related('exercise').order_by('order')
    return render(request, 'routine_form.html', {
        'form': None,
        'title': f'Edit Routine: {routine.name}',
        'object': routine,
        'all_exercises': all_exercises,
        'routine_exercises': existing_routine_exercises # Pass existing for form pre-fill
    })

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
        description = request.POST.get('description', '')
        is_public_str = request.POST.get('is_public', 'off') # Checkbox value is 'on' or not present
        is_public = True if is_public_str == 'on' else False

        if not name:
            # Handle error
            return render(request, 'program_form.html', {
                'title': 'Create New Program',
                'error': 'Name is required.',
                'name_value': name,
                'description_value': description,
                'is_public_value': is_public
            })

        program = Program.objects.create(
            user=request.user,
            name=name,
            description=description,
            is_public=is_public
        )
        return redirect('routine-list')
    else:
        pass # No initial form data to pass for GET
    return render(request, 'program_form.html', {'title': 'Create New Program'})

@login_required
def program_update(request, program_id):
    program = get_object_or_404(Program, id=program_id, user=request.user)
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description', '')
        is_public_str = request.POST.get('is_public', 'off')
        is_public = True if is_public_str == 'on' else False

        if not name:
            return render(request, 'program_form.html', {
                'title': f'Edit Program: {program.name}',
                'object': program,
                'error': 'Name is required.',
                'name_value': name, # Pass current (erroneous) values back
                'description_value': description,
                'is_public_value': is_public
            })

        program.name = name
        program.description = description
        program.is_public = is_public
        program.save()
        return redirect('routine-list')
    else:
        pass # For GET, object is passed directly
    return render(request, 'program_form.html', {
        'title': f'Edit Program: {program.name}',
        'object': program
    })

@login_required
def program_delete(request, program_id):
    program = get_object_or_404(Program, id=program_id, user=request.user)
    if request.method == 'POST':
        program.delete()
        return redirect('routine-list')
    return render(request, 'program_confirm_delete.html', {
        'object': program,
        'title': f'Delete Program: {program.name}'
    })

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