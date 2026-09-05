from .models import Profile, Message, Notification


def unread_messages_count(request):
    if not request.user or not request.user.is_authenticated:
        return {}

    try:
        user_profile = Profile.objects.get(username=request.user.username)
    except Profile.DoesNotExist:
        return {'unread_messages_count': 0}

    count = Message.objects.filter(recipient=user_profile, is_read=False).count()
    return {'unread_messages_count': count}


def unread_notifications_count(request):
    if not request.user or not request.user.is_authenticated:
        return {}

    try:
        user_profile = Profile.objects.get(username=request.user.username)
    except Profile.DoesNotExist:
        return {'unread_notifications_count': 0}

    count = Notification.objects.filter(recipient=user_profile, is_read=False).count()
    return {'unread_notifications_count': count}