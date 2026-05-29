from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.db.models import Sum, Count
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator

from .models import (
    Profile, Post, Category, Tag,
    Comment, Clap, Bookmark,
    ReadHistory, Notification
)
from .forms import (
    RegisterForm, LoginForm, ProfileForm, PostForm, CommentForm
)


# ───────────────────────────────────────────
# HELPER
# ───────────────────────────────────────────

def create_notification(recipient, sender, notif_type, post=None, comment=None):
    if recipient != sender:
        Notification.objects.create(
            recipient=recipient,
            sender=sender,
            notif_type=notif_type,
            post=post,
            comment=comment,
        )


# ═══════════════════════════════════════════
# AUTH
# ═══════════════════════════════════════════

def register_view(request):
    if request.user.is_authenticated:
        return redirect('profile', username=request.user.username)
    
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            Profile.objects.get_or_create(user=user)
            login(request, user, backend='miniblog.backends.EmailBackend')
            messages.success(request, 'Welcome! Account created successfully.')
            return redirect('profile', username=user.username)
        else:
            
            print(">>> REGISTER FORM ERRORS:", form.errors)
    else:
        form = RegisterForm()
    
    return render(request, 'Authentication/register.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('profile', username=request.user.username)

    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            email    = form.cleaned_data['email'].strip().lower()
            password = form.cleaned_data['password']

            user = authenticate(request, email=email, password=password)

            if user:
                if not user.is_active:
                    messages.error(request, 'This account has been deactivated.')
                else:
                    login(request, user, backend='miniblog.backends.EmailBackend')
                    next_url = request.GET.get('next')
                    return redirect(next_url) if next_url else redirect('profile', username=user.username)
            else:
                messages.error(request, 'Invalid email or password.')
    else:
        form = LoginForm()

    return render(request, 'Authentication/login.html', {'form': form})

# FIX #9: logout GET se nahi, sirf POST se
@login_required
@require_POST
def logout_view(request):
    logout(request)
    return redirect('login')


# ═══════════════════════════════════════════
# POSTS
# ═══════════════════════════════════════════

def post_feed(request):
    # FIX #4: default ordering add kiya
    posts = Post.objects.filter(
        status='published'
    ).select_related('author', 'category').order_by('-created_at')

    tag      = request.GET.get('tag')
    category = request.GET.get('category')
    search   = request.GET.get('search')
    trending = request.GET.get('trending')

    if tag:
        posts = posts.filter(tags__name__iexact=tag)
    if category:
        posts = posts.filter(category__slug=category)
    if search:
        posts = posts.filter(title__icontains=search)
    if trending:
        posts = posts.order_by('-views', '-created_at')

    paginator = Paginator(posts, 10)
    page      = request.GET.get('page')
    posts     = paginator.get_page(page)

    categories = Category.objects.all()
    tags       = Tag.objects.all()[:20]

    return render(request, 'Posts/feed.html', {
        'posts': posts,
        'categories': categories,
        'tags': tags,
        'selected_tag': tag,
        'selected_category': category,
        'search': search,
    })


def post_detail(request, slug):
    post = get_object_or_404(Post, slug=slug, status='published')
    post.increment_views()

    if request.user.is_authenticated:
        ReadHistory.objects.update_or_create(user=request.user, post=post)

    comments    = post.comments.filter(parent=None).select_related('user').prefetch_related('replies__user')
    total_claps = post.claps.aggregate(total=Sum('count'))['total'] or 0
    user_claps  = 0
    is_bookmarked = False

    if request.user.is_authenticated:
        clap_obj      = post.claps.filter(user=request.user).first()
        user_claps    = clap_obj.count if clap_obj else 0
        is_bookmarked = Bookmark.objects.filter(user=request.user, post=post).exists()

    comment_form = CommentForm()

    # FIX #3: template path consistent rakha — 'Posts/' prefix use karo
    return render(request, 'Posts/detail.html', {
        'post': post,
        'comments': comments,
        'comment_form': comment_form,
        'total_claps': total_claps,
        'user_claps': user_claps,
        'is_bookmarked': is_bookmarked,
    })


@login_required
def post_create(request):
    if request.method == 'POST':
        form = PostForm(request.POST, request.FILES)
        print(">>> FORM VALID:", form.is_valid())
        print(">>> FORM ERRORS:", form.errors)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            post.save()
            form.save_m2m()
            messages.success(request, 'Post created successfully!')
            return redirect('post_detail', slug=post.slug)
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
            form.save()
            messages.success(request, 'Post updated!')
            return redirect('post_detail', slug=post.slug)
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
        post.delete()
        messages.success(request, 'Post deleted.')
        return redirect('my_posts')
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
    posts = Post.objects.filter(
        author=request.user
    ).select_related('category').order_by('-created_at')
    return render(request, 'Posts/my_posts.html', {'posts': posts})


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
        comment   = form.save(commit=False)
        comment.user   = request.user
        comment.post   = post
        comment.parent = parent
        comment.save()
        if parent:
            create_notification(parent.user, request.user, 'reply', post=post, comment=comment)
        else:
            create_notification(post.author, request.user, 'comment', post=post, comment=comment)
        messages.success(request, 'Comment added!')
    return redirect('post_detail', slug=slug)


@login_required
def delete_comment(request, pk):
    comment = get_object_or_404(Comment, pk=pk)
    slug    = comment.post.slug
    if comment.user != request.user:
        messages.error(request, 'Permission denied.')
    else:
        comment.delete()
        messages.success(request, 'Comment deleted.')
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

    clap, created = Clap.objects.get_or_create(
        user=request.user, post=post, defaults={'count': count}
    )
    if not created:
        # FIX: already 50 pe ho toh save mat karo — unnecessary DB write avoid
        new_count = min(50, clap.count + count)
        if new_count != clap.count:
            clap.count = new_count
            clap.save(update_fields=['count'])
    if created:
        create_notification(post.author, request.user, 'clap', post=post)

    total = post.claps.aggregate(total=Sum('count'))['total'] or 0
    return JsonResponse({'total_claps': total, 'your_claps': clap.count})


# ═══════════════════════════════════════════
# BOOKMARKS
# ═══════════════════════════════════════════

@login_required
def bookmark_list(request):
    bookmarks = Bookmark.objects.filter(
        user=request.user
    ).select_related('post').order_by('-created_at')
    return render(request, 'Posts/bookmarks.html', {'bookmarks': bookmarks})


@login_required
@require_POST
def bookmark_toggle(request, slug):
    post = get_object_or_404(Post, slug=slug, status='published')
    obj, created = Bookmark.objects.get_or_create(user=request.user, post=post)
    if not created:
        obj.delete()
        bookmarked = False
    else:
        bookmarked = True
    return JsonResponse({'bookmarked': bookmarked})


# ═══════════════════════════════════════════
# PROFILE
# ═══════════════════════════════════════════

def profile_view(request, username):
    user    = get_object_or_404(User, username=username)
    profile = get_object_or_404(Profile, user=user)
    # FIX #7: select_related add kiya for performance
    posts   = Post.objects.filter(
        author=user, status='published'
    ).select_related('category').order_by('-created_at')

    is_following = False
    if request.user.is_authenticated and request.user != user:
        my_profile   = get_object_or_404(Profile, user=request.user)
        is_following = profile.followers.filter(pk=my_profile.pk).exists()

    return render(request, 'Posts/Profile.html', {
        'profile': profile,
        'posts': posts,
        'is_following': is_following,
        'follower_count': profile.followers.count(),
        'following_count': profile.following.count(),
    })


@login_required
def profile_edit(request):
    profile = get_object_or_404(Profile, user=request.user)
    if request.method == 'POST':
        form = ProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated!')
            return redirect('profile', username=request.user.username)
    else:
        form = ProfileForm(instance=profile)
    return render(request, 'Posts/edit.html', {'form': form})


@login_required
@require_POST
def follow_user(request, username):
    target_user = get_object_or_404(User, username=username)
    if target_user == request.user:
        return JsonResponse({'error': 'Cannot follow yourself.'}, status=400)

    my_profile     = get_object_or_404(Profile, user=request.user)
    target_profile = get_object_or_404(Profile, user=target_user)

    if target_profile.followers.filter(pk=my_profile.pk).exists():
        target_profile.followers.remove(my_profile)
        following = False
    else:
        target_profile.followers.add(my_profile)
        create_notification(target_user, request.user, 'follow')
        following = True

    return JsonResponse({
        'following': following,
        'follower_count': target_profile.followers.count()
    })


# ═══════════════════════════════════════════
# NOTIFICATIONS
# ═══════════════════════════════════════════

@login_required
def notification_list(request):
    notifs = Notification.objects.filter(
        recipient=request.user
    ).select_related('sender', 'post').order_by('-created_at')

    # FIX #8: unread_count template mein bhi bhejo (badge ke liye useful)
    unread_count = notifs.filter(is_read=False).count()

    return render(request, 'Notifications/list.html', {
        'notifications': notifs,
        'unread_count': unread_count,
    })


@login_required
@require_POST
def mark_notifications_read(request):
    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    return JsonResponse({'message': 'All marked as read.'})


# ═══════════════════════════════════════════
# READ HISTORY
# ═══════════════════════════════════════════

@login_required
def read_history(request):
    # FIX #5: sirf POST + _method check rakha — cleaner
    if request.method == 'POST' and request.POST.get('_method') == 'DELETE':
        ReadHistory.objects.filter(user=request.user).delete()
        messages.success(request, 'History cleared.')
        return redirect('read_history')

    history = ReadHistory.objects.filter(
        user=request.user
    ).select_related('post').order_by('-read_at')
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