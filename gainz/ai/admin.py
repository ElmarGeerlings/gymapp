from django.contrib import admin
from .models import ConversationLog


@admin.register(ConversationLog)
class ConversationLogAdmin(admin.ModelAdmin):
    list_display = ['session_id', 'user', 'get_message_count', 'program_generated', 'program_accepted', 'error_occurred', 'created_at']
    list_filter = ['program_generated', 'program_accepted', 'error_occurred', 'created_at']
    search_fields = ['session_id', 'user__username', 'error_message']
    readonly_fields = ['created_at', 'updated_at']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')

    fieldsets = (
        ('Basic Info', {
            'fields': ('user', 'session_id', 'created_at', 'updated_at')
        }),
        ('Conversation', {
            'fields': ('conversation_data',),
            'classes': ('collapse',)
        }),
        ('Outcome', {
            'fields': ('program_generated', 'program_accepted', 'error_occurred', 'error_message')
        }),
    )