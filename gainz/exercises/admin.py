from django.contrib import admin
from .models import Exercise, ExerciseCategory, ExerciseAlternativeName


class ExerciseAlternativeNameInline(admin.TabularInline):
    model = ExerciseAlternativeName
    extra = 1


@admin.register(Exercise)
class ExerciseAdmin(admin.ModelAdmin):
    list_display = ['name', 'exercise_type', 'is_custom', 'user', 'get_categories']
    list_filter = ['exercise_type', 'is_custom', 'categories']
    search_fields = ['name', 'description']
    inlines = [ExerciseAlternativeNameInline]

    def get_categories(self, obj):
        return ", ".join([cat.name for cat in obj.categories.all()])
    get_categories.short_description = 'Categories'


@admin.register(ExerciseCategory)
class ExerciseCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'description']
    search_fields = ['name']


@admin.register(ExerciseAlternativeName)
class ExerciseAlternativeNameAdmin(admin.ModelAdmin):
    list_display = ['exercise', 'name', 'is_primary']
    list_filter = ['is_primary', 'exercise__categories']
    search_fields = ['exercise__name', 'name']