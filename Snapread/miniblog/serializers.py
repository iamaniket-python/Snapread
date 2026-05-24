from rest_framework import serializers
from django.contrib.auth.models import User
from .models import (
    Profile, Post, Category, Tag,
    Comment, Clap, Bookmark,
    ReadHistory, Notification
)

class RegisterSerializer(serializers.ModelSerializer):
    password  = serializers.CharField(write_only=True, min_length=8)
    password2 = serializers.CharField(write_only=True, label='Confirm Password')

    class Meta:
        model  = User
        fields = ['username', 'email', 'password', 'password2']

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError('Email already registered.')
        return value

    def validate(self, data):
        if data['password'] != data['password2']:
            raise serializers.ValidationError({'password': 'Passwords do not match.'})
        return data

    def create(self, validated_data):
        validated_data.pop('password2')
        user = User.objects.create_user(**validated_data)
        return user


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)


class UserMinimalSerializer(serializers.ModelSerializer):
    """Lightweight user — used inside nested serializers."""
    class Meta:
        model  = User
        fields = ['id', 'username']


class ProfileSerializer(serializers.ModelSerializer):
    username       = serializers.CharField(source='user.username', read_only=True)
    email          = serializers.CharField(source='user.email',    read_only=True)
    followers_count = serializers.SerializerMethodField()
    following_count = serializers.SerializerMethodField()
    is_following    = serializers.SerializerMethodField()

    class Meta:
        model  = Profile
        fields = [
            'id', 'username', 'email',
            'bio', 'profile_image', 'website',
            'followers_count', 'following_count', 'is_following',
            'created_at',
        ]
        read_only_fields = ['username', 'email', 'created_at']

    def get_followers_count(self, obj):
        return obj.followers.count()

    def get_following_count(self, obj):
        # profiles that this user follows
        return Profile.objects.filter(followers=obj).count()

    def get_is_following(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            try:
                my_profile = Profile.objects.get(user=request.user)
                return obj.followers.filter(pk=my_profile.pk).exists()
            except Profile.DoesNotExist:
                return False
        return False


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model  = Category
        fields = ['id', 'name', 'slug', 'created_at']
        read_only_fields = ['slug', 'created_at']


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Tag
        fields = ['id', 'name', 'created_at']
        read_only_fields = ['created_at']

class PostListSerializer(serializers.ModelSerializer):
    """Compact — used in feeds and lists."""
    author        = UserMinimalSerializer(read_only=True)
    category      = CategorySerializer(read_only=True)
    tags          = TagSerializer(many=True, read_only=True)
    claps_count   = serializers.SerializerMethodField()
    comments_count = serializers.SerializerMethodField()
    is_bookmarked = serializers.SerializerMethodField()

    class Meta:
        model  = Post
        fields = [
            'id', 'author', 'category', 'tags',
            'title', 'slug', 'featured_image',
            'status', 'read_time', 'views',
            'claps_count', 'comments_count', 'is_bookmarked',
            'created_at', 'published_at',
        ]

    def get_claps_count(self, obj):
        return obj.claps.aggregate(
            total=__import__('django.db.models', fromlist=['Sum']).Sum('count')
        )['total'] or 0

    def get_comments_count(self, obj):
        return obj.comments.count()

    def get_is_bookmarked(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.bookmarked_by.filter(user=request.user).exists()
        return False


class PostDetailSerializer(PostListSerializer):
    """Full post — includes content."""
    class Meta(PostListSerializer.Meta):
        fields = PostListSerializer.Meta.fields + ['content', 'updated_at']


class PostCreateSerializer(serializers.ModelSerializer):
    """Used for create and update."""
    tags     = serializers.PrimaryKeyRelatedField(queryset=Tag.objects.all(),     many=True, required=False)
    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all(), required=False, allow_null=True)

    class Meta:
        model  = Post
        fields = [
            'title', 'content', 'category', 'tags',
            'featured_image', 'status',
        ]

    def validate_title(self, value):
        if len(value.strip()) < 5:
            raise serializers.ValidationError('Title must be at least 5 characters.')
        return value

    def validate_content(self, value):
        if len(value.strip()) < 50:
            raise serializers.ValidationError('Content must be at least 50 characters.')
        return value

class CommentSerializer(serializers.ModelSerializer):
    user    = UserMinimalSerializer(read_only=True)
    replies = serializers.SerializerMethodField()

    class Meta:
        model  = Comment
        fields = ['id', 'user', 'comment', 'parent', 'replies', 'created_at', 'updated_at']
        read_only_fields = ['user', 'created_at', 'updated_at']

    def get_replies(self, obj):
        if obj.replies.exists():
            return CommentSerializer(obj.replies.all(), many=True, context=self.context).data
        return []

    def validate_comment(self, value):
        if len(value.strip()) < 1:
            raise serializers.ValidationError('Comment cannot be empty.')
        return value

class ClapSerializer(serializers.ModelSerializer):
    user = UserMinimalSerializer(read_only=True)

    class Meta:
        model  = Clap
        fields = ['id', 'user', 'count', 'created_at']
        read_only_fields = ['user', 'created_at']

    def validate_count(self, value):
        if not (1 <= value <= 50):
            raise serializers.ValidationError('Clap count must be between 1 and 50.')
        return value

class BookmarkSerializer(serializers.ModelSerializer):
    post = PostListSerializer(read_only=True)

    class Meta:
        model  = Bookmark
        fields = ['id', 'post', 'created_at']
        read_only_fields = ['created_at']

class NotificationSerializer(serializers.ModelSerializer):
    sender     = UserMinimalSerializer(read_only=True)
    post_title = serializers.CharField(source='post.title', read_only=True, default=None)
    post_slug  = serializers.CharField(source='post.slug',  read_only=True, default=None)

    class Meta:
        model  = Notification
        fields = [
            'id', 'sender', 'notif_type',
            'post_title', 'post_slug',
            'is_read', 'created_at',
        ]


class ReadHistorySerializer(serializers.ModelSerializer):
    post = PostListSerializer(read_only=True)

    class Meta:
        model  = ReadHistory
        fields = ['id', 'post', 'read_at']