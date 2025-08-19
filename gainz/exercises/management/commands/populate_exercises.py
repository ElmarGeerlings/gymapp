from django.core.management.base import BaseCommand
from gainz.exercises.models import Exercise, ExerciseCategory, ExerciseAlternativeName


class Command(BaseCommand):
    help = 'Populate database with common exercises and their alternative names'

    def handle(self, *args, **options):
        self.stdout.write('Creating exercise categories...')

        # Create categories
        categories = {
            'Chest': ExerciseCategory.objects.get_or_create(name='Chest')[0],
            'Back': ExerciseCategory.objects.get_or_create(name='Back')[0],
            'Shoulders': ExerciseCategory.objects.get_or_create(name='Shoulders')[0],
            'Arms': ExerciseCategory.objects.get_or_create(name='Arms')[0],
            'Legs': ExerciseCategory.objects.get_or_create(name='Legs')[0],
            'Core': ExerciseCategory.objects.get_or_create(name='Core')[0],
            'Cardio': ExerciseCategory.objects.get_or_create(name='Cardio')[0],
        }

        # Define exercises with their alternative names
        exercises_data = [
            {
                'name': 'Bench Press',
                'category': 'Chest',
                'exercise_type': 'primary',
                'description': 'Classic compound chest exercise',
                'alternatives': ['bench', 'barbell bench press', 'flat bench press', 'chest press']
            },
            {
                'name': 'Back Squat',
                'category': 'Legs',
                'exercise_type': 'primary',
                'description': 'Fundamental lower body compound exercise',
                'alternatives': ['squat', 'barbell squat', 'back squat', 'leg press']
            },
            {
                'name': 'Conventional Deadlift',
                'category': 'Back',
                'exercise_type': 'primary',
                'description': 'Posterior chain compound exercise',
                'alternatives': ['deadlift', 'barbell deadlift', 'conventional deadlift', 'romanian deadlift']
            },
            {
                'name': 'Overhead Press',
                'category': 'Shoulders',
                'exercise_type': 'primary',
                'description': 'Vertical pressing movement',
                'alternatives': ['ohp', 'military press', 'shoulder press', 'standing press', 'press']
            },
            {
                'name': 'Barbell Row',
                'category': 'Back',
                'exercise_type': 'secondary',
                'description': 'Horizontal pulling movement',
                'alternatives': ['row', 'barbell row', 'pendlay row', 'bent over row']
            },
            {
                'name': 'Pull-ups',
                'category': 'Back',
                'exercise_type': 'secondary',
                'description': 'Bodyweight vertical pulling exercise',
                'alternatives': ['pull ups', 'pullup', 'pullups', 'chin ups', 'chinup', 'chinups']
            },
            {
                'name': 'Dips',
                'category': 'Chest',
                'exercise_type': 'secondary',
                'description': 'Bodyweight pushing exercise',
                'alternatives': ['dip', 'chest dips', 'tricep dips', 'parallel bar dips']
            },
            {
                'name': 'Incline Bench Press',
                'category': 'Chest',
                'exercise_type': 'secondary',
                'description': 'Inclined chest pressing movement',
                'alternatives': ['incline bench', 'incline press', 'incline barbell press']
            },
            {
                'name': 'Romanian Deadlift',
                'category': 'Legs',
                'exercise_type': 'secondary',
                'description': 'Hip hinge movement focusing on hamstrings',
                'alternatives': ['rdl', 'romanian deadlift', 'stiff leg deadlift', 'straight leg deadlift']
            },
            {
                'name': 'Lat Pulldown',
                'category': 'Back',
                'exercise_type': 'secondary',
                'description': 'Machine-based vertical pulling exercise',
                'alternatives': ['lat pulldown', 'lat pull down', 'pulldown', 'pull down']
            },
            {
                'name': 'Leg Press',
                'category': 'Legs',
                'exercise_type': 'secondary',
                'description': 'Machine-based leg pressing movement',
                'alternatives': ['leg press', 'legpress', 'machine squat']
            },
            {
                'name': 'Push-ups',
                'category': 'Chest',
                'exercise_type': 'accessory',
                'description': 'Bodyweight chest exercise',
                'alternatives': ['push ups', 'pushup', 'pushups', 'press ups', 'pressup']
            },
            {
                'name': 'Lunges',
                'category': 'Legs',
                'exercise_type': 'accessory',
                'description': 'Unilateral leg exercise',
                'alternatives': ['lunge', 'walking lunges', 'reverse lunges', 'forward lunges']
            },
            {
                'name': 'Plank',
                'category': 'Core',
                'exercise_type': 'accessory',
                'description': 'Core stability exercise',
                'alternatives': ['planks', 'forearm plank', 'high plank', 'side plank']
            },
            {
                'name': 'Bicep Curls',
                'category': 'Arms',
                'exercise_type': 'accessory',
                'description': 'Isolation exercise for biceps',
                'alternatives': ['curl', 'curls', 'bicep curl', 'biceps curl', 'arm curl']
            },
            {
                'name': 'Tricep Dips',
                'category': 'Arms',
                'exercise_type': 'accessory',
                'description': 'Bodyweight tricep exercise',
                'alternatives': ['tricep dip', 'triceps dip', 'bench dips', 'chair dips']
            },
            {
                'name': 'Shoulder Press',
                'category': 'Shoulders',
                'exercise_type': 'secondary',
                'description': 'Dumbbell shoulder pressing movement',
                'alternatives': ['dumbbell press', 'dumbbell shoulder press', 'db press', 'db shoulder press']
            },
            {
                'name': 'Lateral Raises',
                'category': 'Shoulders',
                'exercise_type': 'accessory',
                'description': 'Isolation exercise for lateral deltoids',
                'alternatives': ['lateral raise', 'side raises', 'side raise', 'dumbbell lateral raise']
            },
            {
                'name': 'Crunches',
                'category': 'Core',
                'exercise_type': 'accessory',
                'description': 'Basic abdominal exercise',
                'alternatives': ['crunch', 'sit ups', 'situp', 'sit-ups', 'ab crunch']
            },
            {
                'name': 'Running',
                'category': 'Cardio',
                'exercise_type': 'accessory',
                'description': 'Cardiovascular exercise',
                'alternatives': ['run', 'jog', 'treadmill', 'cardio']
            }
        ]

        self.stdout.write('Creating exercises...')
        created_count = 0

        for exercise_data in exercises_data:
            # Create or get the exercise
            exercise, created = Exercise.objects.get_or_create(
                name=exercise_data['name'],
                defaults={
                    'description': exercise_data['description'],
                    'exercise_type': exercise_data['exercise_type']
                }
            )

            if created:
                created_count += 1
                self.stdout.write(f'Created exercise: {exercise.name}')

            # Add category
            category = categories[exercise_data['category']]
            exercise.categories.add(category)

            # Create alternative names
            for alt_name in exercise_data['alternatives']:
                ExerciseAlternativeName.objects.get_or_create(
                    exercise=exercise,
                    name=alt_name
                )

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully created {created_count} new exercises with alternative names!'
            )
        )
