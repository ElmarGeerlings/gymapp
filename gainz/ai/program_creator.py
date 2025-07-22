from gainz.workouts.models import Program, Routine, ProgramRoutine, RoutineExercise, RoutineExerciseSet
from gainz.exercises.models import Exercise


class AIProgramCreator:
    """Converts AI-generated program data into database objects"""

    def create_program_from_ai_data(self, user, program_data):
        """
        Create a complete workout program from AI-generated data

        Expected format:
        {
            "name": "Program Name",
            "description": "Description",
            "scheduling_type": "weekly",
            "routines": [
                {
                    "name": "Day 1: Push",
                    "description": "Chest, shoulders, triceps",
                    "exercises": [
                        {
                            "exercise_name": "Bench Press",
                            "order": 1,
                            "sets": [
                                {"reps": 8, "rpe": 7, "notes": "Warm up set"}
                            ]
                        }
                    ]
                }
            ]
        }
        """

        # Create the main program
        program = Program.objects.create(
            user=user,
            name=program_data.get('name', 'AI Generated Program'),
            description=program_data.get('description', ''),
            scheduling_type=program_data.get('scheduling_type', 'weekly'),
            is_active=False  # User can activate it manually
        )

        # Create routines and link them to the program
        for routine_order, routine_data in enumerate(program_data.get('routines', []), 1):
            routine = self._create_routine_from_data(user, routine_data)

            # Link routine to program
            ProgramRoutine.objects.create(
                program=program,
                routine=routine,
                sequence_order=routine_order
            )

        return program

    def _create_routine_from_data(self, user, routine_data):
        """Create a routine with exercises from AI data"""
        routine = Routine.objects.create(
            user=user,
            name=routine_data.get('name', 'AI Routine'),
            description=routine_data.get('description', '')
        )

        # Create exercises for this routine
        for exercise_data in routine_data.get('exercises', []):
            self._create_routine_exercise_from_data(routine, exercise_data)

        return routine

    def _create_routine_exercise_from_data(self, routine, exercise_data):
        """Create a routine exercise with sets from AI data"""
        exercise_name = exercise_data.get('exercise_name', '')

        # Try to find existing exercise, create if not found
        exercise = self._get_or_create_exercise(exercise_name)

        if not exercise:
            return None

        routine_exercise = RoutineExercise.objects.create(
            routine=routine,
            exercise=exercise,
            order=exercise_data.get('order', 1)
        )

        # Create sets for this exercise
        for set_order, set_data in enumerate(exercise_data.get('sets', []), 1):
            RoutineExerciseSet.objects.create(
                routine_exercise=routine_exercise,
                set_order=set_order,
                target_reps=set_data.get('reps', 8),
                target_rpe=set_data.get('rpe', 7),
                notes=set_data.get('notes', '')
            )

        return routine_exercise

    def _get_or_create_exercise(self, exercise_name):
        """Get existing exercise or create a new one"""
        if not exercise_name:
            return None

        # Try to find existing exercise (case-insensitive)
        exercise = Exercise.objects.filter(name__iexact=exercise_name).first()

        if exercise:
            return exercise

        # Create new exercise if not found
        # Try to map to common exercises
        exercise_mapping = {
            'bench press': {'name': 'Bench Press', 'categories': ['Chest']},
            'squat': {'name': 'Back Squat', 'categories': ['Legs']},
            'deadlift': {'name': 'Conventional Deadlift', 'categories': ['Back']},
            'overhead press': {'name': 'Overhead Press', 'categories': ['Shoulders']},
            'barbell row': {'name': 'Barbell Row', 'categories': ['Back']},
            'pull-ups': {'name': 'Pull-ups', 'categories': ['Back']},
            'pull ups': {'name': 'Pull-ups', 'categories': ['Back']},
            'dips': {'name': 'Dips', 'categories': ['Chest']},
            'incline bench press': {'name': 'Incline Bench Press', 'categories': ['Chest']},
            'leg press': {'name': 'Leg Press', 'categories': ['Legs']},
            'lat pulldown': {'name': 'Lat Pulldown', 'categories': ['Back']},
        }

        exercise_key = exercise_name.lower()
        exercise_info = exercise_mapping.get(exercise_key, {
            'name': exercise_name.title(),
            'categories': ['General']
        })

        # Create the exercise
        exercise = Exercise.objects.create(
            name=exercise_info['name'],
            description=f"AI-generated exercise: {exercise_name}"
        )

        # Add categories if they exist in the system
        for category_name in exercise_info['categories']:
            from gainz.exercises.models import Category
            category, created = Category.objects.get_or_create(name=category_name)
            exercise.categories.add(category)

        return exercise