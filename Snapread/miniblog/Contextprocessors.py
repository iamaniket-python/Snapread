from .models import Notification


def global_context(request):
    """
    Injects unread_count into every template automatically.
    Add to settings.py TEMPLATES[0]['OPTIONS']['context_processors']:
        'blog.context_processors.global_context'
    """
    unread_count = 0
    if request.user.is_authenticated:
        unread_count = Notification.objects.filter(
            recipient=request.user, is_read=False
        ).count()

    return {
        'unread_count': unread_count,
    }