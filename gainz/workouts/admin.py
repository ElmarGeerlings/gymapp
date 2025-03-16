from django.contrib import admin
from .models import Workout, WorkoutExercise, ExerciseSet

class ExerciseSetInline(admin.TabularInline):
    model = ExerciseSet
    extra = 1

class WorkoutExerciseInline(admin.TabularInline):
    model = WorkoutExercise
    extra = 1

class WorkoutAdmin(admin.ModelAdmin):
    inlines = [WorkoutExerciseInline]

class WorkoutExerciseAdmin(admin.ModelAdmin):
    inlines = [ExerciseSetInline]

admin.site.register(Workout, WorkoutAdmin)
admin.site.register(WorkoutExercise, WorkoutExerciseAdmin)
admin.site.register(ExerciseSet)