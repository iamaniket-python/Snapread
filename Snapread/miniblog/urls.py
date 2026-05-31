from django.urls import path
from . import views
from .views import CustomPasswordChangeView

urlpatterns = [

    # ─────────────────────────────────────────
    # AUTH
    # ─────────────────────────────────────────
    path('auth/register/', views.register_view, name='register'),
    path('auth/login/',    views.login_view,    name='login'),
    path('auth/logout/',   views.logout_view,   name='logout'),

    # ─────────────────────────────────────────
    # POSTS
    # ─────────────────────────────────────────
    path('',               views.post_feed,    name='post_feed'),    # HOME = feed
    path('posts/create/',  views.post_create,  name='post_create'),
    path('posts/mine/',    views.my_posts,      name='my_posts'),
    path('posts/<slug:slug>/',         views.post_detail,  name='post_detail'),
    path('posts/<slug:slug>/edit/',    views.post_edit,    name='post_edit'),
    path('posts/<slug:slug>/delete/',  views.post_delete,  name='post_delete'),
    path('posts/<slug:slug>/publish/', views.post_publish, name='post_publish'),

    # ─────────────────────────────────────────
    # COMMENTS
    # ─────────────────────────────────────────
    path('posts/<slug:slug>/comments/', views.add_comment,    name='add_comment'),
    path('comments/<int:pk>/delete/',   views.delete_comment, name='delete_comment'),

    # ─────────────────────────────────────────
    # CLAPS (AJAX)
    # ─────────────────────────────────────────
    path('posts/<slug:slug>/clap/', views.clap_post, name='clap'),

    # ─────────────────────────────────────────
    # BOOKMARKS
    # ─────────────────────────────────────────
    path('bookmarks/',                  views.bookmark_list,   name='bookmark_list'),
    path('posts/<slug:slug>/bookmark/', views.bookmark_toggle, name='bookmark_toggle'),

    # ─────────────────────────────────────────
    # PROFILE
    # ─────────────────────────────────────────
    path('profile/edit/',              views.profile_edit, name='profile_edit'),
    path('profile/<str:username>/',    views.profile_view, name='profile'),
    path('profile/<str:username>/follow/', views.follow_user, name='follow_user'),

    # ─────────────────────────────────────────
    # CATEGORIES & TAGS
    # ─────────────────────────────────────────
    path('categories/', views.category_list, name='category_list'),
    path('tags/',       views.tag_list,      name='tag_list'),

    # ─────────────────────────────────────────
    # NOTIFICATIONS
    # ─────────────────────────────────────────
    path('notifications/',          views.notification_list,      name='notification_list'),
    path('notifications/read-all/', views.mark_notifications_read, name='notifications_read_all'),
    path('notifications/mark-read/', views.mark_notifications_read, name='mark_notifications_read'),
    path('search/', views.search_view, name='search'),

    # ─────────────────────────────────────────
    # READ HISTORY
    # ─────────────────────────────────────────
    path('history/', views.read_history, name='read_history'),

    path('password-change/', CustomPasswordChangeView.as_view(), name='password_change'),
]