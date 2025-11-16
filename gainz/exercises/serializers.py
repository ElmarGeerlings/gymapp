from rest_framework import serializers
from .models import Exercise, ExerciseCategory

class ExerciseCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ExerciseCategory
        fields = ['id', 'name', 'description']

class ExerciseSerializer(serializers.ModelSerializer):
    # Provide a read-only list of category names
    category_names = serializers.StringRelatedField(many=True, source='categories', read_only=True)
    # 'categories' field below will handle write operations (expects list of IDs)

    class Meta:
        model = Exercise
        fields = [
            'id', 
            'name', 
            'description', 
            'categories', # Expects list of category IDs on write
            'category_names', # Read-only list of names
            'is_custom',
            'exercise_type', # Added missing exercise_type field
            'weight_increment', # Per-exercise weight increment (kg)
        ]
        # Optionally, make 'categories' write-only if you only want names on read
        # extra_kwargs = {
        #     'categories': {'write_only': True}
        # } 
