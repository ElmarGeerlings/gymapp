from django.contrib import admin
from .models import (
    Program, Routine, RoutineExercise, RoutineExerciseSet,
    Workout, WorkoutExercise, ExerciseSet, ProgramRoutine,
    UserTimerPreference, ExerciseTimerOverride, PersonalRecord
)

# --- Planning Model Admins ---

class RoutineExerciseSetInline(admin.TabularInline):
    """ Inline for defining planned sets within a RoutineExercise. """
    model = RoutineExerciseSet
    extra = 1 # Show one empty form for a new set
    fields = ('set_number', 'target_reps', 'target_weight', 'target_rpe', 'rest_time_seconds', 'notes')
    # To make it more compact, you could consider using fieldsets or a different layout if it gets too wide.

class RoutineExerciseInline(admin.TabularInline):
    """ Inline for defining exercises within a Routine. """
    model = RoutineExercise
    extra = 1 # Show one empty form
    # Consider adding fields like 'exercise', 'order', 'target_sets', 'target_reps' to readonly_fields or list_display if needed
    fields = ('order', 'exercise', 'routine_specific_exercise_type') # Removed target_sets, target_reps, target_rest_seconds and added routine_specific_exercise_type
    # Autocomplete fields are good for ForeignKeys with many options
    autocomplete_fields = ['exercise']
    # inlines = [RoutineExerciseSetInline] # Cannot nest inlines further in TabularInline directly

class RoutineInline(admin.TabularInline):
    """ Inline for showing routines within a Program. """
    model = Routine
    extra = 0 # Don't show empty forms by default, add routines separately
    fields = ('name', 'description')
    readonly_fields = ('name', 'description') # Make them read-only in the program view
    show_change_link = True # Allow clicking to the full Routine admin page

class ProgramRoutineInline(admin.TabularInline):
    model = ProgramRoutine
    extra = 1
    autocomplete_fields = ['routine']
    fields = ('routine', 'order', 'assigned_day')

@admin.register(Program)
class ProgramAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'is_public', 'is_active')
    list_filter = ('user', 'is_public', 'is_active')
    search_fields = ('name', 'description', 'user__username')
    inlines = [ProgramRoutineInline]
    actions = ['activate_programs', 'deactivate_programs']

    def activate_programs(self, request, queryset):
        for program in queryset:
            program.is_active = True
            program.save() # This will trigger the custom save logic
    activate_programs.short_description = "Activate selected programs"

    def deactivate_programs(self, request, queryset):
        queryset.update(is_active=False)
    deactivate_programs.short_description = "Deactivate selected programs"

@admin.register(Routine)
class RoutineAdmin(admin.ModelAdmin):
    list_display = ('name', 'user')
    list_filter = ('user',)
    search_fields = ('name', 'description', 'user__username')
    inlines = [RoutineExerciseInline]
    autocomplete_fields = ['user']

@admin.register(RoutineExercise)
class RoutineExerciseAdmin(admin.ModelAdmin):
    list_display = ('routine', 'exercise', 'order', 'routine_specific_exercise_type')
    list_filter = ('routine', 'exercise', 'routine_specific_exercise_type')
    search_fields = ('routine__name', 'exercise__name')
    list_editable = ('order', 'routine_specific_exercise_type')
    autocomplete_fields = ['routine', 'exercise']
    inlines = [RoutineExerciseSetInline]

@admin.register(ProgramRoutine)
class ProgramRoutineAdmin(admin.ModelAdmin):
    list_display = ('program', 'routine', 'order', 'assigned_day')
    list_filter = ('program', 'routine', 'assigned_day')
    search_fields = ('program__name', 'routine__name')
    autocomplete_fields = ['program', 'routine']

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

# --- Timer Preference Model Admins ---

@admin.register(UserTimerPreference)
class UserTimerPreferenceAdmin(admin.ModelAdmin):
    list_display = ('user', 'primary_timer_seconds', 'secondary_timer_seconds', 'accessory_timer_seconds', 'auto_start_timer', 'timer_sound_enabled')
    list_filter = ('auto_start_timer', 'timer_sound_enabled')
    search_fields = ('user__username', 'user__email')
    autocomplete_fields = ['user']
    fieldsets = (
        ('Default Timer Settings', {
            'fields': ('user', 'primary_timer_seconds', 'secondary_timer_seconds', 'accessory_timer_seconds')
        }),
        ('Timer Behavior', {
            'fields': ('auto_start_timer', 'timer_sound_enabled')
        }),
    )

@admin.register(ExerciseTimerOverride)
class ExerciseTimerOverrideAdmin(admin.ModelAdmin):
    list_display = ('user', 'exercise', 'timer_seconds')
    list_filter = ('user', 'exercise__exercise_type')
    search_fields = ('user__username', 'exercise__name')
    autocomplete_fields = ['user', 'exercise']

@admin.register(PersonalRecord)
class PersonalRecordAdmin(admin.ModelAdmin):
    list_display = ('user', 'exercise', 'record_type', 'weight', 'reps', 'date_achieved')
    list_filter = ('record_type', 'exercise', 'date_achieved')
    search_fields = ('user__username', 'exercise__name')
    ordering = ('-date_achieved',)
    readonly_fields = ('date_achieved', 'get_estimated_1rm')
    autocomplete_fields = ['user', 'exercise']

# Remove the old simple registrations
# admin.site.register(Workout, WorkoutAdmin)
# admin.site.register(WorkoutExercise, WorkoutExerciseAdmin)
# admin.site.register(ExerciseSet)