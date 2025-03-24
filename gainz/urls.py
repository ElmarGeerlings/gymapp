from django.urls import reverse_lazy
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from gainz.views import (
    home,  # your homepage view
    WorkoutViewSet, 
    WorkoutExerciseViewSet, 
    ExerciseSetViewSet,
    ExerciseCategoryViewSet, 
    ExerciseViewSet, 
    workout_detail,
    workout_list,
    exercise_list
)
from django.contrib import admin

# API router setup
router = DefaultRouter()
router.register(r'exercises/categories', ExerciseCategoryViewSet)
router.register(r'exercises', ExerciseViewSet, basename='exercise')
router.register(r'workouts', WorkoutViewSet, basename='workout')
router.register(r'workouts/exercises', WorkoutExerciseViewSet, basename='workout-exercise')
router.register(r'workouts/sets', ExerciseSetViewSet, basename='exercise-set')

# Define urlpatterns as a list
urlpatterns = [
    # Homepage
    path('', home, name='home'),
    
    # Admin site
    path('admin/', admin.site.urls),
    
    # API endpoints
    path('api/', include(router.urls)),
    
    # Nested API endpoints
    path('api/workouts/exercises/<int:workout_exercise_id>/sets/', 
         ExerciseSetViewSet.as_view({'post': 'create'}), 
         name='exercise-set-create'),
    
    # Template views
    path('workouts/<int:workout_id>/', workout_detail, name='workout-detail'),
    
    # Workout list
    path('workouts/', workout_list, name='workout-list'),
    
    # Exercise list
    path('exercises/', exercise_list, name='exercise-list'),
]
