import uuid
import os
from io import BytesIO
from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify
from django.utils import timezone
from django.core.files.base import ContentFile


# ─────────────────────────────────────────
# PROFILE
# ─────────────────────────────────────────
class Profile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        db_index=True
    )
    bio = models.TextField(blank=True, null=True)
    profile_image = models.ImageField(
        upload_to='profiles/',
        blank=True,
        null=True,
        max_length=500
    )
    website = models.URLField(blank=True, null=True)

    followers = models.ManyToManyField(
        'self',
        symmetrical=False,
        related_name='following',
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['created_at']),
        ]

    def save(self, *args, **kwargs):
        if self.profile_image:
            try:
                from PIL import Image
                img = Image.open(self.profile_image)

                if img.mode in ('RGBA', 'P', 'LA'):
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                    img = background
                elif img.mode != 'RGB':
                    img = img.convert('RGB')

                max_size = (400, 400)
                img.thumbnail(max_size, Image.LANCZOS)

                buffer = BytesIO()
                img.save(buffer, format='JPEG', quality=85, optimize=True)
                buffer.seek(0)

                name = os.path.splitext(self.profile_image.name)[0]
                self.profile_image.save(
                    f"{name}.jpg",
                    ContentFile(buffer.read()),
                    save=False
                )
            except Exception:
                pass

        super().save(*args, **kwargs)

    @property
    def avatar_url(self):
        try:
            if self.profile_image and self.profile_image.name:
                return self.profile_image.url
        except Exception:
            pass
        return '/static/img/avatar.png'

    def __str__(self):
        return self.user.username


# ─────────────────────────────────────────
# CATEGORY
# ─────────────────────────────────────────
class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['slug']),
            models.Index(fields=['created_at']),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


# ─────────────────────────────────────────
# TAG
# ─────────────────────────────────────────
class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['name']),
        ]

    def __str__(self):
        return self.name


# ─────────────────────────────────────────
# POST
# ─────────────────────────────────────────
class Post(models.Model):

    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('published', 'Published'),
    )

    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='posts'
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    tags = models.ManyToManyField(Tag, blank=True)

    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, blank=True, max_length=300)
    featured_image = models.ImageField(
        upload_to='posts/',
        blank=True,
        null=True
    )
    content = models.TextField()

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft'
    )

    views = models.PositiveIntegerField(default=0)
    read_time = models.PositiveSmallIntegerField(default=1)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['created_at']),
            models.Index(fields=['published_at']),
            models.Index(fields=['author', 'status']),
            models.Index(fields=['category', 'status']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['status', 'views']),
            models.Index(fields=['status', 'published_at']),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)
            slug = base_slug
            while Post.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{uuid.uuid4().hex[:6]}"
            self.slug = slug

        word_count = len(self.content.split())
        self.read_time = max(1, round(word_count / 200))

        if self.status == 'published' and not self.published_at:
            self.published_at = timezone.now()

        super().save(*args, **kwargs)

    def increment_views(self):
        from django.db.models import F
        Post.objects.filter(pk=self.pk).update(views=F('views') + 1)

    @property
    def featured_image_url(self):
        try:
            if self.featured_image and self.featured_image.name:
                return self.featured_image.url
        except Exception:
            pass
        return None

    def __str__(self):
        return self.title


# ─────────────────────────────────────────
# COMMENT  (with threading)
# ─────────────────────────────────────────
class Comment(models.Model):
    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name='comments'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='comments'
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='replies'
    )

    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['post', 'created_at']),
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['parent']),
        ]

    def is_reply(self):
        return self.parent is not None

    def __str__(self):
        return f"{self.user.username} on '{self.post.title}'"


# ─────────────────────────────────────────
# CLAP
# ─────────────────────────────────────────
class Clap(models.Model):
    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name='claps'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='claps'
    )
    count = models.PositiveSmallIntegerField(default=1)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('post', 'user')
        constraints = [
            models.CheckConstraint(
                condition=models.Q(count__gte=1) & models.Q(count__lte=50),
                name='clap_count_between_1_and_50'
            )
        ]
        indexes = [
            models.Index(fields=['post', 'user']),
            models.Index(fields=['post', 'created_at']),
        ]

    def __str__(self):
        return f"{self.user.username} clapped {self.count}x on '{self.post.title}'"


# ─────────────────────────────────────────
# BOOKMARK
# ─────────────────────────────────────────
class Bookmark(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='bookmarks'
    )
    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name='bookmarked_by'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'post')
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['user', 'post']),
        ]

    def __str__(self):
        return f"{self.user.username} bookmarked '{self.post.title}'"


# ─────────────────────────────────────────
# READ HISTORY
# ─────────────────────────────────────────
class ReadHistory(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='read_history'
    )
    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name='read_by'
    )
    read_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'post')
        indexes = [
            models.Index(fields=['user', 'read_at']),
        ]

    def __str__(self):
        return f"{self.user.username} read '{self.post.title}'"


# ─────────────────────────────────────────
# NOTIFICATION
# ─────────────────────────────────────────
class Notification(models.Model):

    NOTIF_TYPES = (
        ('clap',    'Clap'),
        ('comment', 'Comment'),
        ('reply',   'Reply'),
        ('follow',  'Follow'),
        ('mention', 'Mention'),
    )

    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    sender = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='sent_notifications'
    )
    notif_type = models.CharField(max_length=20, choices=NOTIF_TYPES)

    post = models.ForeignKey(
        Post,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notifications'
    )
    comment = models.ForeignKey(
        Comment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notifications'
    )

    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read']),
            models.Index(fields=['recipient', 'created_at']),
        ]

    def __str__(self):
        return f"{self.sender.username} → {self.recipient.username} [{self.notif_type}]"