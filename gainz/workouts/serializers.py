from rest_framework import serializers
from gainz.workouts.models import Workout, WorkoutExercise, ExerciseSet

class ExerciseSetSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExerciseSet
        fields = ['id', 'set_number', 'reps', 'weight', 'is_warmup', 'is_completed', 'is_amrap']

class WorkoutExerciseSerializer(serializers.ModelSerializer):
    sets = ExerciseSetSerializer(many=True, read_only=True)
    exercise_name = serializers.CharField(source='exercise.name', read_only=True)
    exercise_type_display = serializers.SerializerMethodField()

    class Meta:
        model = WorkoutExercise
        fields = ['id', 'exercise', 'exercise_name', 'order', 'notes', 'sets', 'performance_feedback', 'exercise_type', 'exercise_type_display']

    def get_exercise_type_display(self, obj):
        """Return the exercise type using get_exercise_type() method"""
        return obj.get_exercise_type()

class WorkoutSerializer(serializers.ModelSerializer):
    exercises = WorkoutExerciseSerializer(many=True, read_only=True)

    class Meta:
        model = Workout
        fields = ['id', 'date', 'name', 'notes', 'duration', 'exercises']
