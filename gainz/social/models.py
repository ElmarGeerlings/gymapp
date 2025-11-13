from django.db import models
from django.conf import settings
from django.contrib.auth.models import User


class UserProfile(models.Model):
    """Extended user profile with social features and preferences"""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='social_profile'
    )
    bio = models.TextField(max_length=500, blank=True, help_text="Tell others about yourself")
    profile_picture = models.URLField(
        max_length=500,
        null=True, 
        blank=True, 
        help_text="Profile picture URL"
    )
    
    # Privacy settings
    is_private = models.BooleanField(
        default=False, 
        help_text="If true, workouts are private by default"
    )
    show_personal_records = models.BooleanField(
        default=True, 
        help_text="Show personal records to other users"
    )
    show_workout_details = models.BooleanField(
        default=True, 
        help_text="Show detailed workout information (sets, reps, weights)"
    )
    
    # Social preferences
    allow_comments = models.BooleanField(
        default=True, 
        help_text="Allow others to comment on your workouts"
    )
    email_on_follow = models.BooleanField(
        default=True, 
        help_text="Send email notification when someone follows you"
    )
    email_on_comment = models.BooleanField(
        default=True, 
        help_text="Send email notification when someone comments on your workout"
    )
    
    # Metadata
    date_joined_social = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"
    
    def __str__(self):
        return f"{self.user.username}'s Profile"
    
    def get_followers_count(self):
        """Get count of users following this user"""
        return UserFollow.objects.filter(following=self.user).count()
    
    def get_following_count(self):
        """Get count of users this user is following"""
        return UserFollow.objects.filter(follower=self.user).count()
    
    def is_following(self, target_user):
        """Check if this user is following target_user"""
        return UserFollow.objects.filter(
            follower=self.user, 
            following=target_user
        ).exists()


class UserFollow(models.Model):
    """Follow relationship between users (one-way like Twitter/Instagram)"""
    follower = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='following'
    )
    following = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='followers'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('follower', 'following')
        verbose_name = "User Follow"
        verbose_name_plural = "User Follows"
    
    def __str__(self):
        return f"{self.follower.username} follows {self.following.username}"
    
    def clean(self):
        """Prevent users from following themselves"""
        from django.core.exceptions import ValidationError
        if self.follower == self.following:
            raise ValidationError("Users cannot follow themselves.")


class WorkoutLike(models.Model):
    """Like/reaction on workouts"""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE,
        related_name='workout_likes'
    )
    workout = models.ForeignKey(
        'workouts.Workout', 
        on_delete=models.CASCADE,
        related_name='likes'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('user', 'workout')
        verbose_name = "Workout Like"
        verbose_name_plural = "Workout Likes"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} likes {self.workout.name}"


class WorkoutComment(models.Model):
    """Comments on workouts"""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE,
        related_name='workout_comments'
    )
    workout = models.ForeignKey(
        'workouts.Workout', 
        on_delete=models.CASCADE,
        related_name='comments'
    )
    content = models.TextField(max_length=1000, help_text="Comment content")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Support for comment replies (optional - can add later)
    parent_comment = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='replies'
    )
    
    class Meta:
        verbose_name = "Workout Comment"
        verbose_name_plural = "Workout Comments"
        ordering = ['created_at']  # Chronological order
    
    def __str__(self):
        return f"Comment by {self.user.username} on {self.workout.name}"
    
    def is_reply(self):
        """Check if this comment is a reply to another comment"""
        return self.parent_comment is not None
    
    def get_replies(self):
        """Get all replies to this comment"""
        return self.replies.all().order_by('created_at')


# Signal to create UserProfile when User is created
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Create UserProfile when User is created"""
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Save UserProfile when User is saved"""
    if hasattr(instance, 'social_profile'):
        instance.social_profile.save()