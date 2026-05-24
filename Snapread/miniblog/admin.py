from django.contrib import admin
from .models import (
    Profile, Category, Tag, Post,
    Comment, Clap, Bookmark,
    ReadHistory, Notification
)


# ═══════════════════════════════════════════
# PROFILE
# ═══════════════════════════════════════════

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display  = ['user', 'website', 'created_at']
    search_fields = ['user__username', 'user__email']
    raw_id_fields = ['user']


# ═══════════════════════════════════════════
# CATEGORY
# ═══════════════════════════════════════════

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display  = ['name', 'slug', 'created_at']
    search_fields = ['name']
    prepopulated_fields = {'slug': ('name',)}


# ═══════════════════════════════════════════
# TAG
# ═══════════════════════════════════════════

@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display  = ['name', 'created_at']
    search_fields = ['name']


# ═══════════════════════════════════════════
# POST
# ═══════════════════════════════════════════

class CommentInline(admin.TabularInline):
    model  = Comment
    extra  = 0
    fields = ['user', 'comment', 'created_at']
    readonly_fields = ['created_at']


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display   = ['title', 'author', 'category', 'status', 'views', 'read_time', 'created_at']
    list_filter    = ['status', 'category', 'created_at']
    search_fields  = ['title', 'author__username', 'content']
    prepopulated_fields = {'slug': ('title',)}
    raw_id_fields  = ['author', 'category']
    filter_horizontal = ['tags']
    readonly_fields   = ['views', 'read_time', 'created_at', 'updated_at', 'published_at']
    inlines           = [CommentInline]

    actions = ['publish_posts', 'unpublish_posts']

    def publish_posts(self, request, queryset):
        from django.utils import timezone
        updated = queryset.filter(status='draft').update(
            status='published', published_at=timezone.now()
        )
        self.message_user(request, f'{updated} post(s) published.')
    publish_posts.short_description = 'Publish selected posts'

    def unpublish_posts(self, request, queryset):
        updated = queryset.filter(status='published').update(status='draft')
        self.message_user(request, f'{updated} post(s) moved to draft.')
    unpublish_posts.short_description = 'Move selected posts to draft'


# ═══════════════════════════════════════════
# COMMENT
# ═══════════════════════════════════════════

@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display  = ['user', 'post', 'parent', 'created_at']
    list_filter   = ['created_at']
    search_fields = ['user__username', 'comment', 'post__title']
    raw_id_fields = ['user', 'post', 'parent']


# ═══════════════════════════════════════════
# CLAP
# ═══════════════════════════════════════════

@admin.register(Clap)
class ClapAdmin(admin.ModelAdmin):
    list_display  = ['user', 'post', 'count', 'created_at']
    search_fields = ['user__username', 'post__title']
    raw_id_fields = ['user', 'post']


# ═══════════════════════════════════════════
# BOOKMARK
# ═══════════════════════════════════════════

@admin.register(Bookmark)
class BookmarkAdmin(admin.ModelAdmin):
    list_display  = ['user', 'post', 'created_at']
    search_fields = ['user__username', 'post__title']
    raw_id_fields = ['user', 'post']


# ═══════════════════════════════════════════
# READ HISTORY
# ═══════════════════════════════════════════

@admin.register(ReadHistory)
class ReadHistoryAdmin(admin.ModelAdmin):
    list_display  = ['user', 'post', 'read_at']
    search_fields = ['user__username', 'post__title']
    raw_id_fields = ['user', 'post']


# ═══════════════════════════════════════════
# NOTIFICATION
# ═══════════════════════════════════════════

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display  = ['recipient', 'sender', 'notif_type', 'is_read', 'created_at']
    list_filter   = ['notif_type', 'is_read', 'created_at']
    search_fields = ['recipient__username', 'sender__username']
    raw_id_fields = ['recipient', 'sender', 'post', 'comment']

    actions = ['mark_as_read']

    def mark_as_read(self, request, queryset):
        updated = queryset.update(is_read=True)
        self.message_user(request, f'{updated} notification(s) marked as read.')
    mark_as_read.short_description = 'Mark selected as read'