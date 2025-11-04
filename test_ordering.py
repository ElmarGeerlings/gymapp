#!/usr/bin/env python
"""
Simple test script to verify the exercise ordering logic
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, os.path.dirname(__file__))
django.setup()

from gainz.workouts.models import Workout, WorkoutExercise
from gainz.exercises.models import Exercise
from django.contrib.auth.models import User

def test_ordering_logic():
    print("Testing exercise ordering logic...")

    # Create a test user if it doesn't exist
    user, created = User.objects.get_or_create(
        username='testuser',
        defaults={'email': 'test@example.com'}
    )

    # Create a test workout
    workout, created = Workout.objects.get_or_create(
        name='Test Workout',
        user=user,
        defaults={'date': '2024-01-01'}
    )

    # Create some test exercises
    exercises = []
    for name, ex_type in [
        ('Bench Press', 'primary'),
        ('Squat', 'primary'),
        ('Deadlift', 'primary'),
        ('Pull-ups', 'secondary'),
        ('Rows', 'secondary'),
        ('Dips', 'secondary'),
        ('Curls', 'accessory'),
        ('Tricep Extensions', 'accessory')
    ]:
        exercise, created = Exercise.objects.get_or_create(
            name=name,
            defaults={'exercise_type': ex_type}
        )
        exercises.append(exercise)

    # Clear existing workout exercises
    workout.exercises.all().delete()

    # Add exercises in order to simulate existing workout
    workout_exercises = []
    for i, exercise in enumerate(exercises):
        we = WorkoutExercise.objects.create(
            workout=workout,
            exercise=exercise,
            order=i
        )
        workout_exercises.append(we)

    print("Created workout with exercises:")
    for we in workout_exercises:
        print(f"  {we.exercise.name} ({we.get_exercise_type()}) - order: {we.order}")

    # Test the ordering logic by simulating adding new exercises
    from gainz.views import WorkoutViewSet

    viewset = WorkoutViewSet()
    viewset.request = type('Request', (), {'user': user})()

    # Test cases
    test_cases = [
        # (new_exercise_name, current_exercise_index, expected_description)
        ('Overhead Press', 0, 'Add primary while viewing first primary'),
        ('Lunges', 3, 'Add secondary while viewing first secondary'),
        ('Face Pulls', 3, 'Add accessory while viewing first secondary'),
        ('Push-ups', 6, 'Add primary while viewing accessory'),
    ]

    for new_ex_name, current_idx, description in test_cases:
        # Find the new exercise
        try:
            new_ex = Exercise.objects.get(name=new_ex_name)
        except Exercise.DoesNotExist:
            # Create it if it doesn't exist
            new_ex = Exercise.objects.create(name=new_ex_name, exercise_type='primary')

        current_ex_id = workout_exercises[current_idx].id if current_idx < len(workout_exercises) else None

        # Calculate order
        new_order = viewset._calculate_exercise_order(workout, new_ex.id, current_ex_id)

        print(f"\n{description}:")
        print(f"  Adding {new_ex.name} ({new_ex.exercise_type}) while viewing {workout_exercises[current_idx].exercise.name if current_idx < len(workout_exercises) else 'none'}")
        print(f"  Calculated order: {new_order}")

        # Show where it would be inserted
        existing_orders = [we.order for we in workout_exercises]
        existing_orders.append(new_order)
        existing_orders.sort()

        position = existing_orders.index(new_order) + 1
        print(f"  Would be inserted at position: {position}")

if __name__ == '__main__':
    test_ordering_logic()
