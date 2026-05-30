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


def Notifications_processor(request):
    if request.user.is_authenticated:
        # pehle filter karo, phir slice lo
        all_notifs = request.user.notifications.order_by('-created_at')
        unread_count = all_notifs.filter(is_read=False).count()
        notifs = all_notifs[:5]  # slice BAAD mein
        return {
            'notifications': notifs,
            'unread_count': unread_count,
        }
    return {}