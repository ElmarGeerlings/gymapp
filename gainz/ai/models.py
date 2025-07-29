from django.db import models
from django.contrib.auth.models import User


class ConversationLog(models.Model):
    """Store AI conversations for debugging and analysis"""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    session_id = models.CharField(max_length=100)
    conversation_data = models.JSONField(default=dict)  # Store the full conversation history
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Outcome tracking
    program_generated = models.BooleanField(default=False)
    program_accepted = models.BooleanField(default=False)
    error_occurred = models.BooleanField(default=False)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Conversation {self.session_id[:8]} - {self.user.username} - {self.created_at}"

    def get_message_count(self):
        return len(self.conversation_data) if self.conversation_data else 0

    def get_last_user_message(self):
        if not self.conversation_data:
            return ""
        user_messages = [msg['content'] for msg in self.conversation_data if msg.get('role') == 'user']
        return user_messages[-1] if user_messages else ""