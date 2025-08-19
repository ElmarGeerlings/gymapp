from gainz.workouts.models import Program, Routine, ProgramRoutine, RoutineExercise, RoutineExerciseSet
from gainz.exercises.models import Exercise, ExerciseAlternativeName
import re


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
        print(f"[DEBUG] Creating program with data: {program_data}")
        print(f"[DEBUG] Routines count: {len(program_data.get('routines', []))}")

        # Create the main program
        program = Program.objects.create(
            user=user,
            name=program_data.get('name', 'AI Generated Program'),
            description=program_data.get('description', ''),
            scheduling_type=program_data.get('scheduling_type', 'weekly'),
            is_active=False  # User can activate it manually
        )
        print(f"[DEBUG] Program created: {program.id} - {program.name}")

        # Create routines and link them to the program
        routines_created = 0
        for routine_order, routine_data in enumerate(program_data.get('routines', []), 1):
            print(f"[DEBUG] Creating routine {routine_order}: {routine_data.get('name', 'Unknown')}")
            try:
                routine = self._create_routine_from_data(user, routine_data)
                if routine:
                    # Parse day information from routine name
                    assigned_day = self._parse_day_from_routine_name(routine_data.get('name', ''))

                    # Link routine to program
                    ProgramRoutine.objects.create(
                        program=program,
                        routine=routine,
                        order=routine_order,
                        assigned_day=assigned_day
                    )
                    routines_created += 1
                    print(f"[DEBUG] Routine {routine_order} created successfully with day {assigned_day}")
                else:
                    print(f"[DEBUG] Failed to create routine {routine_order}")
            except Exception as e:
                print(f"[DEBUG] Error creating routine {routine_order}: {e}")

        print(f"[DEBUG] Total routines created: {routines_created}")
        return program

    def _create_routine_from_data(self, user, routine_data):
        """Create a routine with exercises from AI data"""
        print(f"[DEBUG] Creating routine: {routine_data.get('name', 'Unknown')}")
        print(f"[DEBUG] Exercises count: {len(routine_data.get('exercises', []))}")

        routine = Routine.objects.create(
            user=user,
            name=routine_data.get('name', 'AI Routine'),
            description=routine_data.get('description', '')
        )
        print(f"[DEBUG] Routine created: {routine.id} - {routine.name}")

        # Create exercises for this routine
        exercises_created = 0
        for exercise_data in routine_data.get('exercises', []):
            try:
                result = self._create_routine_exercise_from_data(routine, exercise_data)
                if result:
                    exercises_created += 1
                    print(f"[DEBUG] Exercise created: {exercise_data.get('exercise_name', 'Unknown')}")
                else:
                    print(f"[DEBUG] Failed to create exercise: {exercise_data.get('exercise_name', 'Unknown')}")
            except Exception as e:
                print(f"[DEBUG] Error creating exercise {exercise_data.get('exercise_name', 'Unknown')}: {e}")

        print(f"[DEBUG] Total exercises created for routine {routine.name}: {exercises_created}")
        return routine

    def _create_routine_exercise_from_data(self, routine, exercise_data):
        """Create a routine exercise with sets from AI data"""
        exercise_name = exercise_data.get('exercise_name', '')
        print(f"[DEBUG] Creating exercise: {exercise_name}")

        # Try to find existing exercise, create if not found
        exercise = self._find_or_create_exercise(exercise_name)

        if not exercise:
            print(f"[DEBUG] Failed to get/create exercise: {exercise_name}")
            return None

        print(f"[DEBUG] Exercise found/created: {exercise.name} (ID: {exercise.id})")

        routine_exercise = RoutineExercise.objects.create(
            routine=routine,
            exercise=exercise,
            order=exercise_data.get('order', 1)
        )
        print(f"[DEBUG] RoutineExercise created: {routine_exercise.id}")

        # Create sets for this exercise
        sets_created = 0
        for set_order, set_data in enumerate(exercise_data.get('sets', []), 1):
            try:
                RoutineExerciseSet.objects.create(
                    routine_exercise=routine_exercise,
                    set_number=set_order,
                    target_reps=str(set_data.get('reps', 8)),
                    target_rpe=set_data.get('rpe', 7),
                    notes=set_data.get('notes', '')
                )
                sets_created += 1
                print(f"[DEBUG] Set {set_order} created: {set_data.get('reps', 8)} reps @ RPE {set_data.get('rpe', 7)}")
            except Exception as e:
                print(f"[DEBUG] Error creating set {set_order}: {e}")

        print(f"[DEBUG] Total sets created for {exercise_name}: {sets_created}")
        return routine_exercise

    def _find_or_create_exercise(self, exercise_name):
        """Enhanced exercise finding with fuzzy matching and alternative names"""
        if not exercise_name:
            return None

        # Clean the exercise name
        clean_name = self._clean_exercise_name(exercise_name)
        print(f"[DEBUG] Looking for exercise: '{exercise_name}' (cleaned: '{clean_name}')")

        # First, try exact match (case-insensitive)
        exercise = Exercise.objects.filter(name__iexact=clean_name).first()
        if exercise:
            print(f"[DEBUG] Found exact match: {exercise.name}")
            return exercise

        # Try matching with alternative names
        for alt_name in ExerciseAlternativeName.objects.all():
            if alt_name.name.lower() == clean_name.lower():
                print(f"[DEBUG] Found alternative name match: {alt_name.exercise.name}")
                return alt_name.exercise

        # Try fuzzy matching with existing exercises
        exercise = self._fuzzy_match_exercise(clean_name)
        if exercise:
            print(f"[DEBUG] Found fuzzy match: {exercise.name}")
            return exercise

        # If no match found, create a new exercise
        print(f"[DEBUG] No match found, creating new exercise: {clean_name}")
        return self._create_new_exercise(clean_name)

    def _clean_exercise_name(self, name):
        """Clean exercise name for better matching"""
        # Remove extra whitespace and convert to title case
        cleaned = re.sub(r'\s+', ' ', name.strip())
        return cleaned.title()

    def _fuzzy_match_exercise(self, search_name):
        """Fuzzy match exercise names"""
        search_name_lower = search_name.lower()

        # Get all exercises with their alternative names
        all_exercises = Exercise.objects.all()

        best_match = None
        best_score = 0

        for exercise in all_exercises:
            # Check main name
            score = self._calculate_similarity(search_name_lower, exercise.name.lower())
            if score > best_score:
                best_score = score
                best_match = exercise

            # Check alternative names
            for alt_name in exercise.alternative_names.all():
                score = self._calculate_similarity(search_name_lower, alt_name.name.lower())
                if score > best_score:
                    best_score = score
                    best_match = exercise

        # Return match if similarity is high enough (70% or more)
        if best_score >= 0.7:
            print(f"[DEBUG] Fuzzy match found with {best_score:.2f} similarity: {best_match.name}")
            return best_match

        return None

    def _calculate_similarity(self, str1, str2):
        """Calculate similarity between two strings (simple implementation)"""
        # Simple similarity calculation
        if str1 == str2:
            return 1.0

        # Check if one contains the other
        if str1 in str2 or str2 in str1:
            return 0.8

        # Check for common words
        words1 = set(str1.split())
        words2 = set(str2.split())

        if words1 and words2:
            intersection = words1.intersection(words2)
            union = words1.union(words2)
            if union:
                return len(intersection) / len(union)

        return 0.0

    def _create_new_exercise(self, exercise_name):
        """Create a new exercise with appropriate category"""
        # Determine category based on exercise name
        category_name = self._determine_category(exercise_name)

        # Get or create category
        from gainz.exercises.models import ExerciseCategory
        category, created = ExerciseCategory.objects.get_or_create(name=category_name)

        # Create the exercise
        exercise = Exercise.objects.create(
            name=exercise_name,
            description=f"AI-generated exercise: {exercise_name}",
            exercise_type='accessory'  # Default to accessory for new exercises
        )

        # Add category
        exercise.categories.add(category)

        # Add the original name as an alternative name
        ExerciseAlternativeName.objects.create(
            exercise=exercise,
            name=exercise_name
        )

        print(f"[DEBUG] Created new exercise: {exercise.name} in category {category_name}")
        return exercise

    def _determine_category(self, exercise_name):
        """Determine exercise category based on name"""
        name_lower = exercise_name.lower()

        # Define category keywords
        categories = {
            'Chest': ['bench', 'press', 'push', 'chest', 'pec'],
            'Back': ['pull', 'row', 'deadlift', 'back', 'lat'],
            'Shoulders': ['shoulder', 'deltoid', 'lateral', 'ohp', 'military'],
            'Arms': ['curl', 'bicep', 'tricep', 'arm'],
            'Legs': ['squat', 'lunge', 'leg', 'calf', 'thigh'],
            'Core': ['crunch', 'plank', 'situp', 'ab', 'core'],
            'Cardio': ['run', 'jog', 'cardio', 'treadmill', 'bike']
        }

        # Find matching category
        for category, keywords in categories.items():
            for keyword in keywords:
                if keyword in name_lower:
                    return category

        # Default to 'General' if no match
        return 'General'

    def _parse_day_from_routine_name(self, routine_name):
        """Parse day of week from routine name and return day number (0=Monday, 6=Sunday)"""
        if not routine_name:
            return None

        routine_name_lower = routine_name.lower()

        # Map day names to day numbers (Monday=0, Sunday=6)
        day_mapping = {
            'monday': 0, 'mon': 0,
            'tuesday': 1, 'tue': 1, 'tues': 1,
            'wednesday': 2, 'wed': 2,
            'thursday': 3, 'thu': 3, 'thurs': 3,
            'friday': 4, 'fri': 4,
            'saturday': 5, 'sat': 5,
            'sunday': 6, 'sun': 6
        }

        # Check for day names in the routine name
        for day_name, day_number in day_mapping.items():
            if day_name in routine_name_lower:
                print(f"[DEBUG] Found day '{day_name}' in routine name '{routine_name}', assigning day {day_number}")
                return day_number

        # If no day found, return None (will be treated as sequential)
        print(f"[DEBUG] No day found in routine name '{routine_name}', no day assignment")
        return None