from rest_framework import serializers
from gainz.workouts.models import Workout, WorkoutExercise, ExerciseSet

class ExerciseSetSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExerciseSet
        fields = ['id', 'set_number', 'reps', 'weight', 'is_warmup']

class WorkoutExerciseSerializer(serializers.ModelSerializer):
    sets = ExerciseSetSerializer(many=True, read_only=True)
    exercise_name = serializers.CharField(source='exercise.name', read_only=True)

    class Meta:
        model = WorkoutExercise
        fields = ['id', 'exercise', 'exercise_name', 'order', 'notes', 'sets', 'performance_feedback']

class WorkoutSerializer(serializers.ModelSerializer):
    exercises = WorkoutExerciseSerializer(many=True, read_only=True)

    class Meta:
        model = Workout
        fields = ['id', 'date', 'name', 'notes', 'duration', 'exercises'] 