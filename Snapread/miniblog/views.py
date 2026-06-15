from django.core.cache import cache
import logging

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.db.models import Q, Sum, Count
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator
from django.contrib.auth.views import PasswordChangeView
from django.urls import reverse_lazy
from django.contrib.auth.forms import SetPasswordForm
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.core.exceptions import PermissionDenied

from .models import (
    Profile, Post, Category, Tag,
    Comment, Clap, Bookmark,
    ReadHistory, Notification
)
from .forms import (
    RegisterForm, LoginForm, ProfileForm, PostForm, CommentForm
)

logger = logging.getLogger(__name__)


# ───────────────────────────────────────────
# CUSTOM ERROR HANDLERS
# ───────────────────────────────────────────

def custom_404(request, exception=None):
    """Custom 404 Page Not Found handler."""
    return render(request, 'posts/404.html', status=404)


def custom_500(request):
    """Custom 500 Internal Server Error handler."""
    return render(request, 'posts/500.html', status=500)



# ───────────────────────────────────────────
# HELPER
# ───────────────────────────────────────────

def create_notification(recipient, sender, notif_type, post=None, comment=None):
    """
    Create a notification only if recipient and sender are different users.
    Wrapped in try/except to avoid breaking main flow on notification failure.
    """
    if recipient == sender:
        return
    try:
        Notification.objects.create(
            recipient=recipient,
            sender=sender,
            notif_type=notif_type,
            post=post,
            comment=comment,
        )
    except Exception as e:
        logger.error(f"[Notification Error] type={notif_type}, recipient={recipient}, sender={sender}: {e}")


# ═══════════════════════════════════════════
# AUTH
# ═══════════════════════════════════════════

@never_cache
def register_view(request):
    if request.user.is_authenticated:
        return redirect('profile', username=request.user.username)

    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            try:
                user = form.save()
                Profile.objects.get_or_create(user=user)
                login(request, user, backend='miniblog.backends.EmailBackend')
                messages.success(request, 'Welcome! Account created successfully.')
                logger.info(f"[Register] New user registered: {user.username}")
                return redirect('profile', username=user.username)
            except Exception as e:
                logger.error(f"[Register Error] {e}")
                messages.error(request, 'Something went wrong. Please try again.')
        else:
            logger.warning(f"[Register] Form errors: {form.errors}")
    else:
        form = RegisterForm()

    return render(request, 'Authentication/register.html', {'form': form})


@never_cache
def login_view(request):
    if request.user.is_authenticated:
        return redirect('profile', username=request.user.username)

    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            email    = form.cleaned_data['email'].strip().lower()
            password = form.cleaned_data['password']
            user     = authenticate(request, email=email, password=password)

            if user:
                if not user.is_active:
                    messages.error(request, 'This account has been deactivated.')
                else:
                    login(request, user, backend='miniblog.backends.EmailBackend')
                    logger.info(f"[Login] User logged in: {user.username}")
                    next_url = request.GET.get('next')
                    # Security: sirf safe internal URLs allow karo
                    if next_url and next_url.startswith('/'):
                        return redirect(next_url)
                    return redirect('profile', username=user.username)
            else:
                logger.warning(f"[Login] Failed attempt for email: {email}")
                messages.error(request, 'Invalid email or password.')
    else:
        form = LoginForm()

    return render(request, 'Authentication/login.html', {'form': form})


@login_required
@require_POST
@never_cache
def logout_view(request):
    username = request.user.username
    logout(request)
    logger.info(f"[Logout] User logged out: {username}")
    return redirect('login')


# ═══════════════════════════════════════════
# POSTS
# ═══════════════════════════════════════════

def post_feed(request):
    posts = Post.objects.filter(
        status='published'
    ).select_related('author', 'author__profile', 'category').prefetch_related(
        'tags'
    ).order_by('-created_at')

    tag      = request.GET.get('tag', '').strip()
    category = request.GET.get('category', '').strip()
    search   = request.GET.get('search', '').strip()
    trending = request.GET.get('trending')

    if tag:
        posts = posts.filter(tags__name__iexact=tag)
    if category:
        posts = posts.filter(category__slug=category)
    if search:
        posts = posts.filter(
            Q(title__icontains=search) | Q(author__username__icontains=search)
        )
    if trending:
        posts = posts.order_by('-views', '-created_at')

    matched_users = None
    if search:
        matched_users = User.objects.filter(
            username__icontains=search
        ).select_related('profile')[:5]

    paginator = Paginator(posts, 10)
    page      = request.GET.get('page')
    posts     = paginator.get_page(page)

    # ✅ Cached tags (5 min)
    tags = cache.get('feed_tags')
    if tags is None:
        tags = list(Tag.objects.annotate(post_count=Count('post')).order_by('-post_count')[:20])
        cache.set('feed_tags', tags, 300)

    # ✅ Cached categories (5 min)
    categories = cache.get('feed_categories')
    if categories is None:
        categories = list(Category.objects.all())
        cache.set('feed_categories', categories, 300)

    return render(request, 'Posts/feed.html', {
        'posts':             posts,
        'categories':        categories,
        'tags':              tags,
        'selected_tag':      tag,
        'selected_category': category,
        'search':            search,
        'matched_users':     matched_users,
    })

def post_detail(request, slug):
    post = get_object_or_404(
        Post.objects.select_related('author', 'author__profile', 'category'),
        slug=slug,
        status='published'
    )
    post.increment_views()

    has_image = bool(post.featured_image and post.featured_image.name)

    if request.user.is_authenticated:
        ReadHistory.objects.update_or_create(user=request.user, post=post)

    comments    = post.comments.filter(parent=None).select_related('user').prefetch_related('replies__user')
    total_claps = post.claps.aggregate(total=Sum('count'))['total'] or 0
    user_claps  = 0
    is_bookmarked = False
    is_following  = False

    if request.user.is_authenticated:
        clap_obj      = post.claps.filter(user=request.user).first()
        user_claps    = clap_obj.count if clap_obj else 0
        is_bookmarked = Bookmark.objects.filter(user=request.user, post=post).exists()
        if request.user != post.author:
            my_profile     = get_object_or_404(Profile, user=request.user)
            author_profile = get_object_or_404(Profile, user=post.author)
            is_following   = author_profile.followers.filter(pk=my_profile.pk).exists()

    comment_form = CommentForm()

    return render(request, 'Posts/detail.html', {
        'post':          post,
        'comments':      comments,
        'comment_form':  comment_form,
        'total_claps':   total_claps,
        'user_claps':    user_claps,
        'is_bookmarked': is_bookmarked,
        'is_following':  is_following,
        'has_image':     has_image,
    })


@login_required
def post_create(request):
    if request.method == 'POST':
        form = PostForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                post        = form.save(commit=False)
                post.author = request.user
                post.save()
                form.save_m2m()
                logger.info(f"[Post Create] User={request.user.username}, slug={post.slug}")
                messages.success(request, 'Post created successfully!')
                return redirect('post_detail', slug=post.slug)
            except Exception as e:
                logger.error(f"[Post Create Error] {e}")
                messages.error(request, 'Could not create post. Please try again.')
    else:
        form = PostForm()
    return render(request, 'Posts/create.html', {'form': form, 'action': 'Create'})


@login_required
def post_edit(request, slug):
    post = get_object_or_404(Post, slug=slug)

    if post.author != request.user:
        messages.error(request, 'You cannot edit this post.')
        return redirect('post_detail', slug=slug)

    if request.method == 'POST':
        form = PostForm(request.POST, request.FILES, instance=post)
        if form.is_valid():
            try:
                form.save()
                logger.info(f"[Post Edit] User={request.user.username}, slug={post.slug}")
                messages.success(request, 'Post updated!')
                return redirect('post_detail', slug=post.slug)
            except Exception as e:
                logger.error(f"[Post Edit Error] {e}")
                messages.error(request, 'Could not update post. Please try again.')
    else:
        form = PostForm(instance=post)

    return render(request, 'Posts/create.html', {'form': form, 'action': 'Edit', 'post': post})


@login_required
def post_delete(request, slug):
    post = get_object_or_404(Post, slug=slug)

    if post.author != request.user:
        messages.error(request, 'You cannot delete this post.')
        return redirect('post_detail', slug=slug)

    if request.method == 'POST':
        try:
            post.delete()
            logger.info(f"[Post Delete] User={request.user.username}, slug={slug}")
            messages.success(request, 'Post deleted.')
            return redirect('profile', username=request.user.username)
        except Exception as e:
            logger.error(f"[Post Delete Error] {e}")
            messages.error(request, 'Could not delete post.')
            return redirect('post_detail', slug=slug)

    return render(request, 'Posts/delete_confirm.html', {'post': post})


@login_required
def post_publish(request, slug):
    post = get_object_or_404(Post, slug=slug)

    if post.author != request.user:
        messages.error(request, 'Permission denied.')
        return redirect('my_posts')

    if post.status == 'draft':
        post.status = 'published'
        post.save(update_fields=['status'])
        messages.success(request, 'Post published!')
    else:
        post.status = 'draft'
        post.save(update_fields=['status'])
        messages.success(request, 'Post moved to drafts.')

    return redirect('post_detail', slug=post.slug)


@login_required
def my_posts(request):
    filter_by = request.GET.get('filter', 'all')

    posts = Post.objects.filter(
        author=request.user
    ).select_related('category').annotate(
        total_claps=Sum('claps__count')
    ).order_by('-created_at')

    if filter_by == 'published':
        posts = posts.filter(status='published')
    elif filter_by == 'draft':
        posts = posts.filter(status='draft')

    all_posts       = Post.objects.filter(author=request.user)
    published_count = all_posts.filter(status='published').count()
    draft_count     = all_posts.filter(status='draft').count()

    return render(request, 'Posts/my_posts.html', {
        'posts':           posts,
        'filter':          filter_by,
        'published_count': published_count,
        'draft_count':     draft_count,
    })


# ═══════════════════════════════════════════
# COMMENTS
# ═══════════════════════════════════════════

@login_required
@require_POST
def add_comment(request, slug):
    post = get_object_or_404(Post, slug=slug, status='published')
    form = CommentForm(request.POST)

    if form.is_valid():
        parent_id = request.POST.get('parent')
        parent    = get_object_or_404(Comment, id=parent_id, post=post) if parent_id else None

        try:
            comment        = form.save(commit=False)
            comment.user   = request.user
            comment.post   = post
            comment.parent = parent
            comment.save()

            if parent:
                create_notification(parent.user, request.user, 'reply', post=post, comment=comment)
            else:
                create_notification(post.author, request.user, 'comment', post=post, comment=comment)

            messages.success(request, 'Comment added!')
        except Exception as e:
            logger.error(f"[Comment Error] {e}")
            messages.error(request, 'Comment add nahi ho saka. Try again.')
    else:
        messages.error(request, 'Invalid comment.')

    return redirect('post_detail', slug=slug)


@login_required
def delete_comment(request, pk):
    comment = get_object_or_404(Comment, pk=pk)
    slug    = comment.post.slug

    if comment.user != request.user:
        messages.error(request, 'Permission denied.')
    else:
        try:
            comment.delete()
            messages.success(request, 'Comment deleted.')
        except Exception as e:
            logger.error(f"[Comment Delete Error] {e}")
            messages.error(request, 'Comment delete nahi hua.')

    return redirect('post_detail', slug=slug)


# ═══════════════════════════════════════════
# CLAPS — AJAX
# ═══════════════════════════════════════════

@login_required
@require_POST
def clap_post(request, slug):
    post  = get_object_or_404(Post, slug=slug, status='published')
    count = int(request.POST.get('count', 1))
    count = max(1, min(count, 50))

    try:
        clap, created = Clap.objects.get_or_create(
            user=request.user, post=post, defaults={'count': count}
        )
        if not created:
            new_count = min(50, clap.count + count)
            if new_count != clap.count:
                clap.count = new_count
                clap.save(update_fields=['count'])

        if created:
            create_notification(post.author, request.user, 'clap', post=post)

        total = post.claps.aggregate(total=Sum('count'))['total'] or 0
        return JsonResponse({
            'total_claps': total,
            'your_claps':  clap.count,
            'clapped':     True,
        })
    except Exception as e:
        logger.error(f"[Clap Error] {e}")
        return JsonResponse({'error': 'Something went wrong.'}, status=500)


# ═══════════════════════════════════════════
# BOOKMARKS
# ═══════════════════════════════════════════

@login_required
def bookmark_list(request):
    bookmarks = Bookmark.objects.filter(
        user=request.user
    ).select_related('post', 'post__author', 'post__category').order_by('-created_at')
    return render(request, 'Posts/bookmarks.html', {'bookmarks': bookmarks})


@login_required
@require_POST
def bookmark_toggle(request, slug):
    post = get_object_or_404(Post, slug=slug, status='published')

    try:
        obj, created = Bookmark.objects.get_or_create(user=request.user, post=post)
        if not created:
            obj.delete()
            bookmarked = False
        else:
            bookmarked = True

        # Agar bookmark page se aaya hai toh redirect karo
        referer = request.META.get('HTTP_REFERER', '')
        if '/bookmarks/' in referer:
            return redirect('bookmark_list')

        return JsonResponse({'bookmarked': bookmarked})
    except Exception as e:
        logger.error(f"[Bookmark Error] {e}")
        return JsonResponse({'error': 'Something went wrong.'}, status=500)


# ═══════════════════════════════════════════
# PROFILE
# ═══════════════════════════════════════════

def profile_view(request, username):
    user    = get_object_or_404(User, username=username)
    profile = get_object_or_404(Profile, user=user)

    tab = request.GET.get('tab', 'posts')

    # Draft bhi dikhao agar apna profile hai
    if request.user.is_authenticated and request.user == user:
        posts_qs = Post.objects.filter(
            author=user
        ).select_related('category').annotate(
            total_claps=Sum('claps__count')
        ).order_by('-created_at')
    else:
        posts_qs = Post.objects.filter(
            author=user, status='published'
        ).select_related('category').annotate(
            total_claps=Sum('claps__count')
        ).order_by('-created_at')

    paginator = Paginator(posts_qs, 10)
    page      = request.GET.get('page')
    posts     = paginator.get_page(page)

    is_following = False
    if request.user.is_authenticated and request.user != user:
        my_profile   = get_object_or_404(Profile, user=request.user)
        is_following = profile.followers.filter(pk=my_profile.pk).exists()

    user_clapped_slugs    = set()
    user_bookmarked_slugs = set()
    if request.user.is_authenticated:
        user_clapped_slugs = set(
            Clap.objects.filter(user=request.user).values_list('post__slug', flat=True)
        )
        user_bookmarked_slugs = set(
            Bookmark.objects.filter(user=request.user).values_list('post__slug', flat=True)
        )

    return render(request, 'Posts/Profile.html', {
        'profile':               profile,
        'posts':                 posts,
        'tab':                   tab,
        'is_following':          is_following,
        'follower_count':        profile.followers.count(),
        'following_count':       profile.following.count(),
        'user_clapped_slugs':    user_clapped_slugs,
        'user_bookmarked_slugs': user_bookmarked_slugs,
    })


@login_required
def profile_edit(request):
    profile = get_object_or_404(Profile, user=request.user)

    if request.method == 'POST':
        form = ProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, 'Profile updated!')
                return redirect('profile', username=request.user.username)
            except Exception as e:
                logger.error(f"[Profile Edit Error] {e}")
                messages.error(request, 'Profile update nahi ho saka.')
    else:
        form = ProfileForm(instance=profile)

    return render(request, 'Posts/edit.html', {'form': form, 'profile': profile})


@login_required
@require_POST
def follow_user(request, username):
    """
    FIX: Pehle JSON return karta tha — ab AJAX aur normal request dono handle karta hai.
    Agar request AJAX hai (fetch/XMLHttpRequest) toh JSON deta hai,
    warna page ko redirect karta hai.
    """
    target_user = get_object_or_404(User, username=username)

    if target_user == request.user:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': 'Cannot follow yourself.'}, status=400)
        messages.error(request, 'Aap khud ko follow nahi kar sakte.')
        return redirect('profile', username=username)

    try:
        my_profile     = get_object_or_404(Profile, user=request.user)
        target_profile = get_object_or_404(Profile, user=target_user)

        if target_profile.followers.filter(pk=my_profile.pk).exists():
            target_profile.followers.remove(my_profile)
            following = False
        else:
            target_profile.followers.add(my_profile)
            create_notification(target_user, request.user, 'follow')
            following = True

        follower_count = target_profile.followers.count()

        # AJAX request hai toh JSON do
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'following': following, 'follower_count': follower_count})

        # Normal form submit — redirect back to profile
        if following:
            messages.success(request, f'Aap ab {username} ko follow kar rahe hain.')
        else:
            messages.info(request, f'Aapne {username} ko unfollow kar diya.')

        return redirect('profile', username=username)

    except Exception as e:
        logger.error(f"[Follow Error] {e}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': 'Something went wrong.'}, status=500)
        messages.error(request, 'Kuch galat ho gaya. Dobara try karein.')
        return redirect('profile', username=username)


# ═══════════════════════════════════════════
# NOTIFICATIONS
# ═══════════════════════════════════════════

@login_required
def notification_list(request):
    notifs = Notification.objects.filter(
        recipient=request.user
    ).select_related('sender', 'sender__profile', 'post').order_by('-created_at')

    unread_count = notifs.filter(is_read=False).count()

    return render(request, 'Posts/notifications.html', {
        'notifications': notifs,
        'unread_count':  unread_count,
    })


@login_required
@require_POST
def mark_notifications_read(request):
    try:
        updated = Notification.objects.filter(
            recipient=request.user, is_read=False
        ).update(is_read=True)
        logger.info(f"[Notifications] {updated} marked read for {request.user.username}")
    except Exception as e:
        logger.error(f"[Notification Mark Read Error] {e}")
        messages.error(request, 'Notifications mark nahi ho sakin.')
    return redirect('notification_list')


@login_required
def notification_open(request, notif_id):
    notif = get_object_or_404(Notification, id=notif_id, recipient=request.user)

    if not notif.is_read:
        notif.is_read = True
        notif.save(update_fields=['is_read'])

    if notif.notif_type == 'follow':
        return redirect('profile', username=notif.sender.username)

    if notif.post:
        return redirect('post_detail', slug=notif.post.slug)

    return redirect('notification_list')

# ═══════════════════════════════════════════
# SEARCH
# ═══════════════════════════════════════════

def search_view(request):
    query = request.GET.get('search', '').strip()

    posts = []
    users = []

    if query:
        posts = Post.objects.filter(
            status='published'
        ).filter(
            Q(title__icontains=query) | Q(author__username__icontains=query)
        ).select_related('author', 'author__profile', 'category').order_by('-created_at')[:10]

        users = User.objects.filter(
            username__icontains=query
        ).select_related('profile')[:6]

    return render(request, 'Posts/search.html', {
        'query': query,
        'posts': posts,
        'users': users,
    })


# ═══════════════════════════════════════════
# READ HISTORY
# ═══════════════════════════════════════════

@login_required
def read_history(request):
    if request.method == 'POST' and request.POST.get('_method') == 'DELETE':
        try:
            deleted, _ = ReadHistory.objects.filter(user=request.user).delete()
            logger.info(f"[Read History] {deleted} entries cleared for {request.user.username}")
            messages.success(request, 'History cleared.')
        except Exception as e:
            logger.error(f"[Read History Clear Error] {e}")
            messages.error(request, 'History clear nahi ho saki.')
        return redirect('read_history')

    history = ReadHistory.objects.filter(
        user=request.user
    ).select_related('post', 'post__author').order_by('-read_at')

    return render(request, 'Posts/history.html', {'history': history})


# ═══════════════════════════════════════════
# CATEGORIES & TAGS
# ═══════════════════════════════════════════

def category_list(request):
    categories = Category.objects.annotate(post_count=Count('post')).order_by('-post_count')
    return render(request, 'Posts/categories.html', {'categories': categories})


def tag_list(request):
    tags = Tag.objects.annotate(post_count=Count('post')).order_by('-post_count')
    return render(request, 'Posts/tags.html', {'tags': tags})


# ═══════════════════════════════════════════
# PASSWORD CHANGE
# ═══════════════════════════════════════════

class CustomPasswordChangeView(PasswordChangeView):
    template_name = 'Authentication/password_change.html'
    form_class    = SetPasswordForm
    success_url   = reverse_lazy('login')

    def dispatch(self, request, *args, **kwargs):
        return super(PasswordChangeView, self).dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs         = super().get_form_kwargs()
        kwargs['user'] = self.request.user if self.request.user.is_authenticated else None
        return kwargs

    def form_valid(self, form):
        logger.info(f"[Password Change] User={self.request.user.username}")
        messages.success(self.request, 'Password successfully change ho gaya!')
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, 'Kuch galat hua. Dobara try karein.')
        return super().form_invalid(form)