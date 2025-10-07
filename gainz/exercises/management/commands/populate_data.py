from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
import datetime
import random

from gainz.exercises.models import ExerciseCategory, Exercise
from gainz.workouts.models import Program, Routine, RoutineExercise, RoutineExerciseSet, Workout, WorkoutExercise, ExerciseSet

User = get_user_model()

class Command(BaseCommand):
    help = 'Populates the database with sample data for the Gainz application'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user',
            type=str,
            help='Username to create sample data for',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting data population...'))

        # 0. Get the user
        username = options.get('user')
        if username:
            try:
                user = User.objects.get(username=username)
                self.stdout.write(self.style.SUCCESS(f'Creating sample data for user: {user.username}'))
            except User.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'User "{username}" does not exist.'))
                return
        else:
            # If no user specified, get the first superuser or first user
            user = User.objects.filter(is_superuser=True).first() or User.objects.first()
            if not user:
                self.stdout.write(self.style.ERROR('No users exist. Please create a user first.'))
                return
            self.stdout.write(self.style.WARNING(f'No user specified, using: {user.username}'))

        # 1. Create Exercise Categories
        categories_data = [
            {"name": "Chest", "description": "Exercises targeting the pectoral muscles."},
            {"name": "Back", "description": "Exercises targeting the muscles of the back."},
            {"name": "Legs", "description": "Exercises targeting the leg muscles, including quads, hamstrings, and calves."},
            {"name": "Shoulders", "description": "Exercises targeting the deltoid muscles."},
            {"name": "Biceps", "description": "Exercises targeting the biceps."},
            {"name": "Triceps", "description": "Exercises targeting the triceps."},
            {"name": "Core", "description": "Exercises targeting the abdominal and lower back muscles."},
        ]
        categories = {}
        for cat_data in categories_data:
            category, created = ExerciseCategory.objects.get_or_create(name=cat_data["name"], defaults=cat_data)
            categories[cat_data["name"]] = category
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created category: {category.name}'))

        # 2. Create Exercises
        exercises_data = [
            {"name": "Bench Press", "exercise_type": "primary", "categories": [categories["Chest"]], "description": "Compound chest press."},
            {"name": "Overhead Press", "exercise_type": "primary", "categories": [categories["Shoulders"]], "description": "Compound shoulder press."},
            {"name": "Squat", "exercise_type": "primary", "categories": [categories["Legs"]], "description": "Compound leg exercise."},
            {"name": "Deadlift", "exercise_type": "primary", "categories": [categories["Back"], categories["Legs"]], "description": "Compound full body lift."},
            {"name": "Barbell Row", "exercise_type": "primary", "categories": [categories["Back"]], "description": "Compound back exercise."},
            {"name": "Pull Up", "exercise_type": "primary", "categories": [categories["Back"], categories["Biceps"]], "description": "Bodyweight back and bicep exercise."},
            {"name": "Dumbbell Curl", "exercise_type": "accessory", "categories": [categories["Biceps"]], "description": "Isolation exercise for biceps."},
            {"name": "Tricep Pushdown", "exercise_type": "accessory", "categories": [categories["Triceps"]], "description": "Isolation exercise for triceps."},
            {"name": "Leg Press", "exercise_type": "secondary", "categories": [categories["Legs"]], "description": "Machine-based leg exercise."},
            {"name": "Lateral Raise", "exercise_type": "accessory", "categories": [categories["Shoulders"]], "description": "Isolation exercise for lateral deltoids."},
            {"name": "Plank", "exercise_type": "accessory", "categories": [categories["Core"]], "description": "Core stability exercise."},
            {"name": "Leg Extension", "exercise_type": "accessory", "categories": [categories["Legs"]], "description": "Isolation for quads."},
        ]

        created_exercises = {}
        for ex_data in exercises_data:
            ex_cats = ex_data.pop("categories")
            exercise, created = Exercise.objects.get_or_create(
                name=ex_data["name"],
                defaults=ex_data
            )
            if created:
                exercise.categories.set(ex_cats)
                self.stdout.write(self.style.SUCCESS(f'Created exercise: {exercise.name}'))
            created_exercises[exercise.name] = exercise

        # Ensure all base exercises exist for routine creation
        required_ex_for_routine = ["Bench Press", "Squat", "Overhead Press"]
        for ex_name in required_ex_for_routine:
            if ex_name not in created_exercises:
                 # Fallback if somehow not created, though get_or_create should handle it
                default_cat = categories.get("Chest") or ExerciseCategory.objects.first()
                ex, _ = Exercise.objects.get_or_create(name=ex_name, defaults={'exercise_type':'primary', 'description':f'Default {ex_name}'})
                if default_cat:
                    ex.categories.add(default_cat)
                created_exercises[ex_name] = ex
                self.stdout.write(self.style.WARNING(f'Fallback creation for exercise: {ex_name}'))


        # 3. Create a Program
        program, created = Program.objects.get_or_create(
            user=user,
            name="Strength Builder Program",
            defaults={"description": "A beginner to intermediate strength building program."}
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'Created program: {program.name}'))

        # 4. Create a Routine
        routine, created = Routine.objects.get_or_create(
            user=user,
            name="Full Body Workout A",
            defaults={"description": "Full body session focusing on compound lifts."}
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'Created routine: {routine.name}'))

        # 5. Add RoutineExercises
        routine_exercises_data = [
            {"exercise": created_exercises["Squat"], "order": 0, "sets_data": [
                {"set_number": 1, "target_reps": "5-8", "rest_time_seconds": 120},
                {"set_number": 2, "target_reps": "5-8", "rest_time_seconds": 120},
                {"set_number": 3, "target_reps": "5-8", "rest_time_seconds": 120},
            ]},
            {"exercise": created_exercises["Bench Press"], "order": 1, "sets_data": [
                {"set_number": 1, "target_reps": "5-8", "rest_time_seconds": 120},
                {"set_number": 2, "target_reps": "5-8", "rest_time_seconds": 120},
                {"set_number": 3, "target_reps": "5-8", "rest_time_seconds": 120},
            ]},
            {"exercise": created_exercises["Overhead Press"], "order": 2, "sets_data": [
                {"set_number": 1, "target_reps": "8-12", "rest_time_seconds": 90},
                {"set_number": 2, "target_reps": "8-12", "rest_time_seconds": 90},
                {"set_number": 3, "target_reps": "8-12", "rest_time_seconds": 90},
            ]},
        ]
        for i, re_data in enumerate(routine_exercises_data):
             # Ensure exercise exists before trying to create RoutineExercise
            if re_data["exercise"]:
                sets_data = re_data.pop("sets_data", [])
                re, created = RoutineExercise.objects.get_or_create(
                    routine=routine,
                    exercise=re_data["exercise"],
                    order=re_data["order"],
                    defaults={}
                )
                if created:
                    self.stdout.write(self.style.SUCCESS(f'Added {re_data["exercise"].name} to routine {routine.name}'))
                    
                    # Create RoutineExerciseSet objects for this RoutineExercise
                    for set_data in sets_data:
                        res, set_created = RoutineExerciseSet.objects.get_or_create(
                            routine_exercise=re,
                            set_number=set_data["set_number"],
                            defaults={
                                "target_reps": set_data["target_reps"],
                                "rest_time_seconds": set_data.get("rest_time_seconds")
                            }
                        )
                        if set_created:
                            self.stdout.write(self.style.SUCCESS(f'  Added Set {set_data["set_number"]} to {re_data["exercise"].name}'))
            else:
                self.stdout.write(self.style.ERROR(f'Could not add exercise to routine, exercise data missing.'))


        # 6. Create a Workout log
        # Create a workout for today
        workout1_date = timezone.now()
        workout1, created = Workout.objects.get_or_create(
            user=user,
            name="Today's Full Body Session",
            date=workout1_date,
            defaults={
                "notes": "Felt good today, pushed a bit harder on squats.",
                "duration": datetime.timedelta(minutes=60),
                "routine_source": routine
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'Created workout: {workout1.name} on {workout1_date.strftime("%Y-%m-%d")}'))

        # Create a workout for 3 days ago
        workout2_date = timezone.now() - datetime.timedelta(days=3)
        workout2, created = Workout.objects.get_or_create(
            user=user,
            name="Previous Full Body Session",
            date=workout2_date,
            defaults={
                "notes": "Focused on form.",
                "duration": datetime.timedelta(minutes=55),
                "routine_source": routine
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'Created workout: {workout2.name} on {workout2_date.strftime("%Y-%m-%d")}'))

        # 7. Add WorkoutExercises and ExerciseSets
        workouts_to_populate = [workout1, workout2]

        for workout_instance in workouts_to_populate:
            # Use exercises from the routine_source if available
            exercises_for_this_workout = []
            if workout_instance.routine_source:
                source_routine_exercises = RoutineExercise.objects.filter(routine=workout_instance.routine_source).order_by('order')
                for r_ex in source_routine_exercises:
                    exercises_for_this_workout.append({
                        'exercise_model': r_ex.exercise,
                        'order': r_ex.order,
                        'routine_exercise_source': r_ex
                    })
            else: # Fallback to some default exercises if no routine source
                exercises_for_this_workout = [
                    {'exercise_model': created_exercises["Squat"], 'order': 0},
                    {'exercise_model': created_exercises["Bench Press"], 'order': 1},
                ]

            for idx, we_data in enumerate(exercises_for_this_workout):
                base_exercise = we_data['exercise_model']
                exercise_type = base_exercise.exercise_type or 'accessory'
                wo_exercise, created = WorkoutExercise.objects.get_or_create(
                    workout=workout_instance,
                    exercise=base_exercise,
                    order=idx, # use current index for order
                    defaults={
                        'notes': f'Performed {base_exercise.name}',
                        'routine_exercise_source': we_data.get('routine_exercise_source'),
                        'exercise_type': exercise_type,
                    }
                )
                if not created and wo_exercise.exercise_type != exercise_type:
                    wo_exercise.exercise_type = exercise_type
                    wo_exercise.save(update_fields=['exercise_type'])
                if created:
                    self.stdout.write(self.style.SUCCESS(f'Added {base_exercise.name} to workout {workout_instance.name}'))

                    # Add 3 sets for each WorkoutExercise
                    for i in range(1, 4):
                        reps = random.randint(5, 12)
                        weight = round(random.uniform(20.0, 100.0) / 2.5) * 2.5 # Simulate common plate jumps
                        es, es_created = ExerciseSet.objects.get_or_create(
                            workout_exercise=wo_exercise,
                            set_number=i,
                            defaults={
                                'reps': reps,
                                'weight': weight,
                                'is_warmup': True if i == 1 and random.choice([True, False]) else False # Randomly make first set a warmup
                            }
                        )
                        if es_created:
                             self.stdout.write(self.style.SUCCESS(f'  Added Set {i}: {reps} reps @ {weight}kg for {we_data["exercise_model"].name}'))


        self.stdout.write(self.style.SUCCESS('Successfully populated the database with sample data.'))
