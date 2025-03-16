from rest_framework import serializers
from .models import Exercise, ExerciseCategory

class ExerciseCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ExerciseCategory
        fields = ['id', 'name', 'description']

class ExerciseSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = Exercise
        fields = ['id', 'name', 'description', 'category', 'category_name', 'is_custom'] 