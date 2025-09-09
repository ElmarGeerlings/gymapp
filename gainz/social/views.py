from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q, Count, Prefetch
from django.core.paginator import Paginator
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from .models import UserProfile, UserFollow, WorkoutLike, WorkoutComment
from gainz.workouts.models import Workout


@login_required
def social_feed(request):
    """Main social feed showing workouts from followed users"""
    user = request.user
    
    # Get users that current user follows
    following_users = UserFollow.objects.filter(
        follower=user
    ).values_list('following', flat=True)
    
    # Get public workouts from followed users + user's own workouts
    workouts = Workout.objects.filter(
        Q(user__in=following_users, visibility='public') | Q(user=user)
    ).select_related(
        'user', 'routine_source'
    ).prefetch_related(
        'likes', 'comments__user', 'exercises__exercise'
    ).order_by('-date')
    
    # Add like status for each workout
    for workout in workouts:
        workout.user_has_liked = workout.likes.filter(user=user).exists()
    
    # Paginate results
    paginator = Paginator(workouts, 10)  # 10 workouts per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'social/feed.html', {
        'page_obj': page_obj,
        'workouts': page_obj,
    })


@login_required 
def user_profile_view(request, username):
    """View user profile and their public workouts"""
    target_user = get_object_or_404(User, username=username)
    profile = get_object_or_404(UserProfile, user=target_user)
    
    is_own_profile = request.user == target_user
    is_following = False
    
    if not is_own_profile:
        is_following = UserFollow.objects.filter(
            follower=request.user, 
            following=target_user
        ).exists()
    
    # Get workouts - show all if own profile, only public if other's profile
    if is_own_profile:
        workouts = Workout.objects.filter(user=target_user)
    else:
        workouts = Workout.objects.filter(user=target_user, visibility='public')
    
    workouts = workouts.select_related('routine_source').prefetch_related(
        'likes', 'comments'
    ).order_by('-date')[:10]  # Latest 10 workouts
    
    # Get follow counts
    followers_count = UserFollow.objects.filter(following=target_user).count()
    following_count = UserFollow.objects.filter(follower=target_user).count()
    
    return render(request, 'social/profile.html', {
        'target_user': target_user,
        'profile': profile,
        'workouts': workouts,
        'is_own_profile': is_own_profile,
        'is_following': is_following,
        'followers_count': followers_count,
        'following_count': following_count,
    })


@login_required
def user_search(request):
    """Search for users"""
    query = request.GET.get('q', '').strip()
    users = []
    
    if query:
        users = User.objects.filter(
            Q(username__icontains=query) | 
            Q(first_name__icontains=query) | 
            Q(last_name__icontains=query)
        ).select_related('social_profile').exclude(
            id=request.user.id  # Exclude current user
        )[:20]  # Limit to 20 results
        
        # Add follow status for each user
        for user in users:
            user.is_followed_by_current_user = UserFollow.objects.filter(
                follower=request.user, 
                following=user
            ).exists()
    
    return render(request, 'social/user_search.html', {
        'query': query,
        'users': users,
    })


@login_required
def follow_user(request, username):
    """Follow a user"""
    if request.method == 'POST':
        target_user = get_object_or_404(User, username=username)
        
        if target_user == request.user:
            messages.error(request, "You can't follow yourself!")
            return redirect('social:profile', username=username)
        
        follow, created = UserFollow.objects.get_or_create(
            follower=request.user,
            following=target_user
        )
        
        if created:
            messages.success(request, f"You are now following {target_user.username}!")
        else:
            messages.info(request, f"You are already following {target_user.username}")
    
    return redirect('social:profile', username=username)


@login_required
def unfollow_user(request, username):
    """Unfollow a user"""
    if request.method == 'POST':
        target_user = get_object_or_404(User, username=username)
        
        follow = UserFollow.objects.filter(
            follower=request.user,
            following=target_user
        ).first()
        
        if follow:
            follow.delete()
            messages.success(request, f"You have unfollowed {target_user.username}")
        else:
            messages.error(request, f"You are not following {target_user.username}")
    
    return redirect('social:profile', username=username)


# AJAX API Views
@login_required
def api_like_workout(request, workout_id):
    """Like/unlike a workout via AJAX"""
    if request.method == 'POST':
        workout = get_object_or_404(Workout, id=workout_id)
        
        # Check if workout can be viewed by user
        if not workout.can_be_viewed_by(request.user):
            return JsonResponse({'error': 'Workout not accessible'}, status=403)
        
        like, created = WorkoutLike.objects.get_or_create(
            user=request.user,
            workout=workout
        )
        
        if not created:
            # Unlike - remove the like
            like.delete()
            liked = False
        else:
            liked = True
        
        return JsonResponse({
            'liked': liked,
            'like_count': workout.get_like_count()
        })
    
    return JsonResponse({'error': 'Invalid method'}, status=405)


@login_required
def api_add_comment(request, workout_id):
    """Add a comment to a workout via AJAX"""
    if request.method == 'POST':
        workout = get_object_or_404(Workout, id=workout_id)
        
        # Check if workout can be viewed by user
        if not workout.can_be_viewed_by(request.user):
            return JsonResponse({'error': 'Workout not accessible'}, status=403)
        
        # Check if comments are allowed on this workout
        if not workout.user.social_profile.allow_comments:
            return JsonResponse({'error': 'Comments not allowed'}, status=403)
        
        content = request.POST.get('content', '').strip()
        if not content:
            return JsonResponse({'error': 'Comment cannot be empty'}, status=400)
        
        if len(content) > 1000:
            return JsonResponse({'error': 'Comment too long'}, status=400)
        
        comment = WorkoutComment.objects.create(
            user=request.user,
            workout=workout,
            content=content
        )
        
        return JsonResponse({
            'success': True,
            'comment': {
                'id': comment.id,
                'content': comment.content,
                'user': comment.user.username,
                'created_at': comment.created_at.strftime('%Y-%m-%d %H:%M'),
                'comment_count': workout.get_comment_count()
            }
        })
    
    return JsonResponse({'error': 'Invalid method'}, status=405)


@login_required
def api_follow_toggle(request, username):
    """Toggle follow status via AJAX"""
    if request.method == 'POST':
        target_user = get_object_or_404(User, username=username)
        
        if target_user == request.user:
            return JsonResponse({'error': 'Cannot follow yourself'}, status=400)
        
        follow = UserFollow.objects.filter(
            follower=request.user,
            following=target_user
        ).first()
        
        if follow:
            follow.delete()
            following = False
            action = 'unfollowed'
        else:
            UserFollow.objects.create(
                follower=request.user,
                following=target_user
            )
            following = True
            action = 'followed'
        
        # Get updated follower count
        followers_count = UserFollow.objects.filter(following=target_user).count()
        
        return JsonResponse({
            'following': following,
            'action': action,
            'followers_count': followers_count
        })
    
    return JsonResponse({'error': 'Invalid method'}, status=405)


@login_required
def workout_detail_social(request, workout_id):
    """Workout detail view with social features"""
    workout = get_object_or_404(Workout, id=workout_id)
    
    # Check if user can view this workout
    if not workout.can_be_viewed_by(request.user):
        messages.error(request, "You don't have permission to view this workout.")
        return redirect('social:feed')
    
    # Get comments for this workout
    comments = WorkoutComment.objects.filter(
        workout=workout
    ).select_related('user').order_by('created_at')
    
    # Check if current user has liked this workout
    user_has_liked = workout.likes.filter(user=request.user).exists() if request.user.is_authenticated else False
    
    return render(request, 'social/workout_detail.html', {
        'workout': workout,
        'comments': comments,
        'can_comment': workout.user.social_profile.allow_comments,
        'user_has_liked': user_has_liked,
    })