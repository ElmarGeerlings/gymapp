from django.contrib import admin
from .models import (
    Program, Routine, RoutineExercise, 
    Workout, WorkoutExercise, ExerciseSet
)

# --- Planning Model Admins ---

class RoutineExerciseInline(admin.TabularInline):
    """ Inline for defining exercises within a Routine. """
    model = RoutineExercise
    extra = 1 # Show one empty form
    # Consider adding fields like 'exercise', 'order', 'target_sets', 'target_reps' to readonly_fields or list_display if needed
    fields = ('order', 'exercise', 'target_sets', 'target_reps', 'target_rest_seconds', 'notes', 'progression_strategy_notes')
    # Autocomplete fields are good for ForeignKeys with many options
    autocomplete_fields = ['exercise'] 

class RoutineInline(admin.TabularInline):
    """ Inline for showing routines within a Program. """
    model = Routine
    extra = 0 # Don't show empty forms by default, add routines separately
    fields = ('name', 'description')
    readonly_fields = ('name', 'description') # Make them read-only in the program view
    show_change_link = True # Allow clicking to the full Routine admin page

@admin.register(Program)
class ProgramAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'is_public')
    list_filter = ('user', 'is_public')
    search_fields = ('name', 'description', 'user__username')
    inlines = [RoutineInline]

@admin.register(Routine)
class RoutineAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'program')
    list_filter = ('user', 'program')
    search_fields = ('name', 'description', 'program__name', 'user__username')
    inlines = [RoutineExerciseInline]
    # Autocomplete fields are good for ForeignKeys with many options
    autocomplete_fields = ['program', 'user']

@admin.register(RoutineExercise)
class RoutineExerciseAdmin(admin.ModelAdmin):
    list_display = ('routine', 'exercise', 'order', 'target_sets', 'target_reps')
    list_filter = ('routine__program', 'routine', 'exercise')
    search_fields = ('routine__name', 'exercise__name')
    list_editable = ('order',)
    # Autocomplete fields are good for ForeignKeys with many options
    autocomplete_fields = ['routine', 'exercise']

# --- Logging Model Admins ---

class ExerciseSetInline(admin.TabularInline):
    """ Inline for adding/editing sets within a WorkoutExercise log. """
    model = ExerciseSet
    extra = 1 
    fields = ('set_number', 'weight', 'reps', 'is_warmup')

# Removed the WorkoutExerciseInline as it might be confusing within WorkoutAdmin
# It's often better to manage WorkoutExercise logs separately or via the WorkoutExerciseAdmin

@admin.register(Workout)
class WorkoutAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'date', 'routine_source')
    list_filter = ('user', 'date', 'routine_source')
    search_fields = ('name', 'notes', 'user__username', 'routine_source__name')
    date_hierarchy = 'date'
    # Instead of inline, maybe link to related WorkoutExercises?
    # We can refine this later if needed.
    # autocomplete_fields = ['user', 'routine_source'] # Add if user/routine lists get long

@admin.register(WorkoutExercise)
class WorkoutExerciseAdmin(admin.ModelAdmin):
    list_display = ('workout', 'exercise', 'order', 'performance_feedback', 'routine_exercise_source')
    list_filter = ('workout__date', 'exercise', 'performance_feedback', 'workout__routine_source')
    search_fields = ('workout__name', 'exercise__name', 'notes')
    list_editable = ('order', 'performance_feedback')
    inlines = [ExerciseSetInline]
    # Autocomplete fields are good for ForeignKeys with many options
    autocomplete_fields = ['workout', 'exercise', 'routine_exercise_source']

@admin.register(ExerciseSet)
class ExerciseSetAdmin(admin.ModelAdmin):
    list_display = ('workout_exercise', 'set_number', 'weight', 'reps', 'is_warmup')
    list_filter = ('workout_exercise__workout__date', 'is_warmup')
    search_fields = ('workout_exercise__exercise__name', 'workout_exercise__workout__name')
    # Autocomplete fields are good for ForeignKeys with many options
    autocomplete_fields = ['workout_exercise']

# Remove the old simple registrations
# admin.site.register(Workout, WorkoutAdmin)
# admin.site.register(WorkoutExercise, WorkoutExerciseAdmin)
# admin.site.register(ExerciseSet)