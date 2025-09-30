from django.urls import reverse_lazy
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from gainz.ai.views import ai_program_create, ai_conversation, ai_program_finalize
from gainz.views import (
    home,  # your homepage view
    WorkoutViewSet,
    WorkoutExerciseViewSet,
    ExerciseSetViewSet,
    ExerciseCategoryViewSet,
    ExerciseViewSet,
    workout_detail,
    workout_list,
    exercise_list,
    routine_list,
    simple_api_test, # Add our new view here
    routine_detail, # Add routine_detail here
    routine_create, # Add routine_create view
    program_create, # Add program_create view
    routine_update, # Add routine_update view
    routine_delete, # Add routine_delete view
    program_update, # Add program_update view
    program_delete, # Add program_delete view
    program_list, # Add program_list view
    program_activate, # Add program_activate view
    program_deactivate, # Add program_deactivate view
    start_workout_from_routine, # Add start_workout_from_routine view
    start_empty_workout, # Add empty workout view
    clear_workout, # Add clear workout view
    workout_update,
    workout_delete,
    start_next_workout, # Add new view
    # ajax_get_exercise_details,
    ajax_update_workout_exercise_feedback,
    ajax_update_program_scheduling,
    ajax_restore_program_state, # Add restore function
    update_user_preferences, # Add new view for user preferences
    api_timer_preferences, # Add timer preferences API view
    api_exercise_timer_overrides, # Add exercise timer overrides API view
    api_exercise_timer_override_delete, # Add exercise timer override delete API view
    api_exercises_search, # Add exercises search API view
    api_program_timer_preferences, # Add program timer preferences API view
    api_routine_timer_preferences, # Add routine timer preferences API view
    health_check, # Add health check view
    register, # Add register view
    generate_sample_data, # Add sample data generation view
    import_routine, # Add import routine view
    profile, # Add profile view
    progress_overview, # Add progress overview view
    exercise_progress_detail, # Add exercise progress detail view
    api_exercise_chart_data, # Add exercise chart data API view
    api_progress_filter_options, # Add progress filter options API view
    progress_pr_history, # Add personal records history view
)
from django.contrib import admin
from django.contrib.auth import views as auth_views  # Import auth views

# API router setup
router = DefaultRouter()
router.register(r'exercises/categories', ExerciseCategoryViewSet)
router.register(r'exercises', ExerciseViewSet, basename='exercise')
router.register(r'workouts', WorkoutViewSet, basename='workout')
router.register(r'workouts/exercises', WorkoutExerciseViewSet, basename='workout-exercise')
router.register(r'workouts/sets', ExerciseSetViewSet, basename='exercise-set')

# Define urlpatterns as a list
urlpatterns = [
    # Health check for Railway
    path('health/', health_check, name='health-check'),

    # Homepage
    path('', home, name='home'),

    # Admin site
    path('admin/', admin.site.urls),

    # Authentication views
    path('accounts/register/', register, name='register'),  # Added register view
    path('accounts/login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),  # Added login view
    path('accounts/logout/', auth_views.LogoutView.as_view(next_page='home'), name='logout'), # Added logout view
    path('accounts/profile/', profile, name='profile'),  # Added profile view

    # API endpoints
    path('api/', include(router.urls)),

    # Simple API test endpoint
    path('api/simple-test/', simple_api_test, name='simple-api-test'),
    
    # Timer preferences API endpoint
    path('api/timer-preferences/', api_timer_preferences, name='api-timer-preferences'),
    
    # Exercise timer overrides API endpoints
    path('api/exercise-timer-overrides/', api_exercise_timer_overrides, name='api-exercise-timer-overrides'),
    path('api/exercise-timer-overrides/<int:override_id>/delete/', api_exercise_timer_override_delete, name='api-exercise-timer-override-delete'),
    
    # Exercise search API endpoint
    path('api/exercises/search/', api_exercises_search, name='api-exercises-search'),
    
    # Program and routine timer preferences API endpoints
    path('api/programs/<int:program_id>/timer-preferences/', api_program_timer_preferences, name='api-program-timer-preferences'),
    path('api/routines/<int:routine_id>/timer-preferences/', api_routine_timer_preferences, name='api-routine-timer-preferences'),

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

    # Routine list
    path('routines/', routine_list, name='routine-list'),

    # Routine detail
    path('routines/<int:routine_id>/', routine_detail, name='routine-detail'),

    # Create Routine
    path('routines/create/', routine_create, name='routine-create'),
    
    # Import Routine
    path('routines/import/', import_routine, name='import-routine'),

    # Update Routine
    path('routines/<int:routine_id>/edit/', routine_update, name='routine-update'),

    # Delete Routine
    path('routines/<int:routine_id>/delete/', routine_delete, name='routine-delete'),

    # Start Workout from Routine
    path('routines/<int:routine_id>/start-workout/', start_workout_from_routine, name='start-workout-from-routine'),

    # Create Program
    path('programs/create/', program_create, name='program-create'),

    # AI Program Creation
    path('programs/ai-create/', ai_program_create, name='ai-program-create'),
    path('ai/conversation/', ai_conversation, name='ai-conversation'),
    path('ai/finalize/', ai_program_finalize, name='ai-program-finalize'),

    # Program List
    path('programs/', program_list, name='program-list'),

    # Update Program
    path('programs/<int:program_id>/edit/', program_update, name='program-update'),

    # Delete Program
    path('programs/<int:program_id>/delete/', program_delete, name='program-delete'),

    # Activate/Deactivate Program
    path('programs/<int:program_id>/activate/', program_activate, name='program-activate'),
    path('programs/<int:program_id>/deactivate/', program_deactivate, name='program-deactivate'),

    # Update Workout
    path('workouts/<int:workout_id>/edit/', workout_update, name='workout-update'),

    # Delete Workout
    path('workouts/<int:workout_id>/delete/', workout_delete, name='workout-delete'),

    # Clear Workout (remove all exercises)
    path('workouts/<int:workout_id>/clear/', clear_workout, name='clear-workout'),

    # Start Next Workout
    path('workouts/start-next/', start_next_workout, name='start-next-workout'),

    # Start Empty Workout
    path('workouts/start-empty/', start_empty_workout, name='start-empty-workout'),

    # path('ajax/get_exercise_details/', ajax_get_exercise_details, name='ajax_get_exercise_details'),
    path('ajax/update_workout_exercise_feedback/', ajax_update_workout_exercise_feedback, name='ajax_update_workout_exercise_feedback'),
    path('ajax/program/<int:program_id>/update-scheduling/', ajax_update_program_scheduling, name='ajax-update-program-scheduling'),
    path('ajax/program/<int:program_id>/restore-state/', ajax_restore_program_state, name='ajax-restore-program-state'),

    # User Preferences
    path('ajax/update_user_preferences/', update_user_preferences, name='update-user-preferences'),
    
    # Progress Views
    path('progress/', progress_overview, name='progress-overview'),
    path('progress/exercise/<int:exercise_id>/', exercise_progress_detail, name='exercise-progress-detail'),
    path('progress/records/', progress_pr_history, name='progress-pr-history'),

    # Progress API Endpoints
    path('api/progress/filter-options/', api_progress_filter_options, name='api-progress-filter-options'),
    path('api/progress/exercise/<int:exercise_id>/chart-data/', api_exercise_chart_data, name='api-exercise-chart-data'),
    
    # Social Features
    path('social/', include('gainz.social.urls')),
    
    # Development Tools (REMOVE IN PRODUCTION!)
    path('dev/generate-sample-data/', generate_sample_data, name='generate-sample-data'),
]
