from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from gainz.workouts.models import Routine, RoutineExercise, RoutineExerciseSet
from gainz.exercises.models import Exercise, ExerciseAlternativeName
from gainz.workouts.utils.workout_parser import WorkoutParser
from decimal import Decimal

User = get_user_model()


class Command(BaseCommand):
    help = 'Import workout routine from text format'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--user',
            type=str,
            help='Username to associate the routine with',
            required=True
        )
        parser.add_argument(
            '--routine-name',
            type=str,
            help='Name for the routine',
            required=True
        )
        parser.add_argument(
            '--file',
            type=str,
            help='Path to file containing workout text',
            required=False
        )
        parser.add_argument(
            '--text',
            type=str,
            help='Workout text directly as a string',
            required=False
        )
        parser.add_argument(
            '--create-missing',
            action='store_true',
            help='Create exercises that don\'t exist in the database',
            default=False
        )
    
    def handle(self, *args, **options):
        # Get user
        username = options['user']
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'User "{username}" not found'))
            return
        
        # Get workout text
        if options['file']:
            with open(options['file'], 'r') as f:
                workout_text = f.read()
        elif options['text']:
            workout_text = options['text']
        else:
            self.stdout.write(self.style.ERROR('Either --file or --text must be provided'))
            return
        
        # Parse the workout text
        parser = WorkoutParser()
        parsed_exercises = parser.parse_workout_text(workout_text)
        
        if not parsed_exercises:
            self.stdout.write(self.style.ERROR('No exercises could be parsed from the text'))
            return
        
        # Create or get the routine
        routine_name = options['routine_name']
        routine, created = Routine.objects.get_or_create(
            user=user,
            name=routine_name,
            defaults={'description': f'Imported from text on {self.get_current_date()}'}
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'Created new routine: {routine_name}'))
        else:
            self.stdout.write(self.style.WARNING(f'Using existing routine: {routine_name}'))
            # Clear existing exercises if updating
            routine.exercises.all().delete()
        
        # Process each parsed exercise
        exercise_order = 0
        created_exercises = []
        skipped_exercises = []
        
        for parsed_ex in parsed_exercises:
            exercise_name = parsed_ex['exercise_name']
            
            # Find or create the exercise
            exercise = parser.find_or_create_exercise(exercise_name)
            
            if not exercise:
                if options['create_missing']:
                    # Create the exercise
                    exercise = Exercise.objects.create(
                        name=exercise_name,
                        description=f'Auto-created from import',
                        is_custom=True,
                        user=user,
                        exercise_type='accessory'
                    )
                    created_exercises.append(exercise_name)
                    self.stdout.write(self.style.SUCCESS(f'Created new exercise: {exercise_name}'))
                else:
                    skipped_exercises.append(exercise_name)
                    self.stdout.write(self.style.WARNING(f'Skipping unknown exercise: {exercise_name}'))
                    continue
            
            # Create RoutineExercise
            routine_exercise = RoutineExercise.objects.create(
                routine=routine,
                exercise=exercise,
                order=exercise_order
            )
            exercise_order += 1
            
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
            
            if parsed_ex['is_bilateral']:
                self.stdout.write(f'  Added {exercise.name}: {sets} sets x {reps} reps @ {weight or "BW"}kg (bilateral)')
            else:
                self.stdout.write(f'  Added {exercise.name}: {sets} sets x {reps} reps @ {weight or "BW"}kg')
        
        # Summary
        self.stdout.write(self.style.SUCCESS(f'\nRoutine "{routine_name}" has been {"created" if created else "updated"}'))
        self.stdout.write(f'Total exercises: {exercise_order}')
        
        if created_exercises:
            self.stdout.write(self.style.SUCCESS(f'Created {len(created_exercises)} new exercises'))
        
        if skipped_exercises:
            self.stdout.write(self.style.WARNING(f'Skipped {len(skipped_exercises)} unknown exercises'))
            self.stdout.write('Use --create-missing flag to auto-create missing exercises')
    
    def get_current_date(self):
        from datetime import datetime
        return datetime.now().strftime('%Y-%m-%d %H:%M')