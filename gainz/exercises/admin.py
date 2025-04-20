from django.contrib import admin
from .models import Exercise, ExerciseCategory

class ExerciseAdmin(admin.ModelAdmin):
    list_display = ('name', 'exercise_type', 'is_custom', 'display_categories')
    list_filter = ('exercise_type', 'is_custom', 'categories')
    search_fields = ('name', 'description')
    filter_horizontal = ('categories',) # Use filter_horizontal for M2M

    @admin.display(description='Categories')
    def display_categories(self, obj):
        # Display categories in the list view
        return ", ".join([cat.name for cat in obj.categories.all()])

class ExerciseCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)

admin.site.register(Exercise, ExerciseAdmin)
admin.site.register(ExerciseCategory, ExerciseCategoryAdmin)