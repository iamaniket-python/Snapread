from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Profile, Post, Notification


# ═══════════════════════════════════════════
# AUTO-CREATE PROFILE ON USER REGISTRATION
# ═══════════════════════════════════════════

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
  
    if created:
        Profile.objects.get_or_create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    
    try:
        instance.profile.save()
    except Profile.DoesNotExist:
        Profile.objects.create(user=instance)


# ═══════════════════════════════════════════
# NOTIFY FOLLOWERS WHEN AUTHOR PUBLISHES A POST
# ═══════════════════════════════════════════

@receiver(post_save, sender=Post)
def notify_followers_on_publish(sender, instance, created, **kwargs):

    if not created and instance.status == 'published':
        try:
            author_profile = instance.author.profile
            followers      = author_profile.followers.all()  # Profile objects

            notifications = [
                Notification(
                    recipient  = follower.user,
                    sender     = instance.author,
                    notif_type = 'follow',          # reusing follow type — "followed author published"
                    post       = instance,
                )
                for follower in followers
                if follower.user != instance.author  # don't notify yourself
            ]

            if notifications:
                Notification.objects.bulk_create(notifications, ignore_conflicts=True)

        except Exception:
            pass  # never let signals crash the main request


# ═══════════════════════════════════════════
# CLEAN UP NOTIFICATIONS WHEN POST IS DELETED
# ═══════════════════════════════════════════

@receiver(post_delete, sender=Post)
def cleanup_post_notifications(sender, instance, **kwargs):
    """Delete all notifications linked to a deleted post."""
    Notification.objects.filter(post=instance).delete()