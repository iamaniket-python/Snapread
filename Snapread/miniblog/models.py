import uuid
from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify
from django.utils import timezone


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
        null=True
    )
    website = models.URLField(blank=True, null=True)

    # ✅ ADDED: Follow system
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

    # ✅ ADDED: auto read time (minutes)
    read_time = models.PositiveSmallIntegerField(default=1)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            # High-cardinality single fields
            models.Index(fields=['slug']),
            models.Index(fields=['created_at']),
            models.Index(fields=['published_at']),
            # Composite indexes for common feed queries
            models.Index(fields=['author', 'status']),
            models.Index(fields=['category', 'status']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['status', 'views']),       # trending queries
            models.Index(fields=['status', 'published_at']),
        ]

    def save(self, *args, **kwargs):
        # ✅ FIX: Slug collision-safe generation
        if not self.slug:
            base_slug = slugify(self.title)
            slug = base_slug
            while Post.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{uuid.uuid4().hex[:6]}"
            self.slug = slug

        # ✅ ADDED: Auto read time calculation (avg 200 wpm)
        word_count = len(self.content.split())
        self.read_time = max(1, round(word_count / 200))

        # ✅ FIX: Auto-set published_at when status flips to published
        if self.status == 'published' and not self.published_at:
            self.published_at = timezone.now()

        super().save(*args, **kwargs)

    def increment_views(self):
        # ✅ FIX: Race-condition-safe view counter using F() expression
        from django.db.models import F
        Post.objects.filter(pk=self.pk).update(views=F('views') + 1)

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

    # ✅ ADDED: Self-referential parent for threaded replies
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
            models.Index(fields=['parent']),               # fetch replies fast
        ]

    def is_reply(self):
        return self.parent is not None

    def __str__(self):
        return f"{self.user.username} on '{self.post.title}'"


# ─────────────────────────────────────────
# CLAP  (replaces Like — supports 1–50 claps)
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
    # ✅ ADDED: count field like Medium (1 to 50 claps per user per post)
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
# READ HISTORY  ✅ NEW
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
# NOTIFICATION  ✅ NEW
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

    # Optional — not all notifications are post-related (e.g. follow)
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