from django.urls import path
from . import views

app_name = 'social'

urlpatterns = [
    # Main social views
    path('', views.social_feed, name='feed'),
    path('profile/<str:username>/', views.user_profile_view, name='profile'),
    path('search/', views.user_search, name='search'),
    path('workout/<int:workout_id>/', views.workout_detail_social, name='workout_detail'),
    
    # Follow/Unfollow actions
    path('follow/<str:username>/', views.follow_user, name='follow'),
    path('unfollow/<str:username>/', views.unfollow_user, name='unfollow'),
    
    # AJAX API endpoints
    path('api/like/<int:workout_id>/', views.api_like_workout, name='api_like'),
    path('api/comment/<int:workout_id>/', views.api_add_comment, name='api_comment'),
    path('api/follow/<str:username>/', views.api_follow_toggle, name='api_follow_toggle'),
]