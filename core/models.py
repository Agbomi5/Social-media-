from datetime import datetime
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils import timezone
from django.conf import settings


class UserManager(BaseUserManager):
    def create_user(self, username, email=None, password=None, **extra_fields):
        if not username:
            raise ValueError('The given username must be set')

        email = self.normalize_email(email)
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(username, email, password, **extra_fields)


class Profile(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(max_length=255, unique=True)
    username = models.CharField(max_length=50, unique=True)
    age = models.IntegerField(null=True, blank=True)
    profile_image = models.ImageField(upload_to='profiles/', default='blank-profile-picture.png')
    phone_number = models.CharField(max_length=15, unique=True, null=True, blank=True)
    bio = models.TextField(null=True, blank=True)
    address = models.CharField(max_length=50, null=True, blank=True)
    location = models.CharField(max_length=100, null=True, blank=True)
    website = models.URLField(max_length=200, null=True, blank=True)
    is_verified = models.BooleanField(default=False)
    is_private = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    last_active = models.DateTimeField(default=timezone.now)
    followers_count = models.IntegerField(default=0)
    following_count = models.IntegerField(default=0)

    objects = UserManager()

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email']

    class Meta:
        verbose_name = 'user'
        verbose_name_plural = 'users'
        indexes = [
            models.Index(fields=['username']),
            models.Index(fields=['email']),
            models.Index(fields=['-date_joined']),
        ]

    def __str__(self):
        return self.username


class FollowersCount(models.Model):
    follower = models.CharField(max_length=95)
    username = models.ForeignKey(Profile, on_delete=models.CASCADE, max_length=50)

    class Meta:
        unique_together = ('follower', 'username')

    def __str__(self):
        return f"{self.follower} follows {self.username}"


class FollowRequest(models.Model):
    requester = models.ForeignKey(Profile, related_name='follow_requests_sent', on_delete=models.CASCADE)
    target = models.ForeignKey(Profile, related_name='follow_requests_received', on_delete=models.CASCADE)
    created_at = models.DateTimeField(default=timezone.now)
    is_accepted = models.BooleanField(default=False)

    class Meta:
        unique_together = ('requester', 'target')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.requester.username} -> {self.target.username}"


class Block(models.Model):
    blocker = models.ForeignKey(Profile, related_name='blocking', on_delete=models.CASCADE)
    blocked = models.ForeignKey(Profile, related_name='blocked_by', on_delete=models.CASCADE)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ('blocker', 'blocked')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.blocker.username} blocked {self.blocked.username}"


class Hashtag(models.Model):
    name = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(default=timezone.now)
    trending_score = models.IntegerField(default=0)

    class Meta:
        ordering = ['-trending_score', '-created_at']

    def __str__(self):
        return f"#{self.name}"


class Post(models.Model):
    username = models.ForeignKey(Profile, on_delete=models.CASCADE, max_length=30)
    image = models.ImageField(upload_to='posts/', null=True, blank=True)
    video = models.FileField(upload_to='posts/', null=True, blank=True)
    caption = models.TextField()
    location = models.CharField(max_length=200, null=True, blank=True)
    created_at = models.DateTimeField(default=datetime.now)
    is_repost = models.BooleanField(default=False)
    original_post = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='reposts')
    view_count = models.IntegerField(default=0)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['username']),
        ]

    def __str__(self):
        return f"{self.username}'s Post ({self.pk})"

    @property
    def total_reactions(self):
        return self.stickers.count()


class LikePost(models.Model):
    post_id = models.ForeignKey(Post, on_delete=models.CASCADE, max_length=80)
    username = models.ForeignKey(Profile, on_delete=models.CASCADE, max_length=50)

    class Meta:
        unique_together = ('post_id', 'username')


class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(Profile, on_delete=models.CASCADE)
    content = models.TextField()
    created_on = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(null=True, blank=True)
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE, related_name='replies')
    likes = models.ManyToManyField(Profile, related_name='comment_likes', blank=True)
    dislikes = models.ManyToManyField(Profile, related_name='comment_dislikes', blank=True)

    class Meta:
        ordering = ['created_on']
        indexes = [
            models.Index(fields=['post', 'created_on']),
        ]

    @property
    def is_parent(self):
        return self.parent is None

    def __str__(self):
        return f'Comment by {self.author.username}'


class Sticker(models.Model):
    name = models.CharField(max_length=50, unique=True)
    emoji = models.CharField(max_length=8, null=True, blank=True)
    image = models.ImageField(upload_to='stickers/', null=True, blank=True)

    def __str__(self):
        return self.name


class PostSticker(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='stickers')
    user = models.ForeignKey(Profile, on_delete=models.CASCADE)
    sticker = models.ForeignKey(Sticker, on_delete=models.CASCADE)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ('post', 'user')
        indexes = [
            models.Index(fields=['post', '-created_at']),
        ]

    def __str__(self):
        return f'{self.user.username} reacted to post {self.post.id} with {self.sticker.name}'


class CommentSticker(models.Model):
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, related_name='stickers')
    user = models.ForeignKey(Profile, on_delete=models.CASCADE)
    sticker = models.ForeignKey(Sticker, on_delete=models.CASCADE)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ('comment', 'user')

    def __str__(self):
        return f'{self.user.username} reacted to comment {self.comment.id} with {self.sticker.name}'


class Bookmark(models.Model):
    user = models.ForeignKey(Profile, related_name='bookmarks', on_delete=models.CASCADE)
    post = models.ForeignKey(Post, related_name='bookmarked_by', on_delete=models.CASCADE)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ('user', 'post')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} bookmarked post {self.post.id}"


class Repost(models.Model):
    user = models.ForeignKey(Profile, related_name='reposts', on_delete=models.CASCADE)
    original_post = models.ForeignKey(Post, related_name='repost_log', on_delete=models.CASCADE)
    created_at = models.DateTimeField(default=timezone.now)
    caption = models.TextField(null=True, blank=True)

    class Meta:
        unique_together = ('user', 'original_post')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} reposted {self.original_post.id}"


class Story(models.Model):
    user = models.ForeignKey(Profile, related_name='stories', on_delete=models.CASCADE)
    image = models.ImageField(upload_to='stories/', null=True, blank=True)
    video = models.FileField(upload_to='stories/', null=True, blank=True)
    caption = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    is_viewed = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(hours=24)
        super().save(*args, **kwargs)

    def is_expired(self):
        return timezone.now() > self.expires_at

    def __str__(self):
        return f"{self.user.username}'s Story ({self.pk})"


class StoryView(models.Model):
    story = models.ForeignKey(Story, related_name='views', on_delete=models.CASCADE)
    viewer = models.ForeignKey(Profile, related_name='viewed_stories', on_delete=models.CASCADE)
    viewed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ('story', 'viewer')

    def __str__(self):
        return f"{self.viewer.username} viewed {self.story}"


class Notification(models.Model):
    NOTIFICATION_TYPES = (
        ('like', 'Like'),
        ('comment', 'Comment'),
        ('follow', 'Follow'),
        ('repost', 'Repost'),
        ('mention', 'Mention'),
        ('message', 'Message'),
        ('story', 'Story'),
        ('follow_request', 'Follow Request'),
    )

    recipient = models.ForeignKey(Profile, related_name='notifications', on_delete=models.CASCADE)
    sender = models.ForeignKey(Profile, related_name='sent_notifications', on_delete=models.CASCADE, null=True, blank=True)
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    post = models.ForeignKey(Post, null=True, blank=True, on_delete=models.CASCADE)
    comment = models.ForeignKey(Comment, null=True, blank=True, on_delete=models.CASCADE)
    message = models.ForeignKey('Message', null=True, blank=True, on_delete=models.CASCADE)
    story = models.ForeignKey(Story, null=True, blank=True, on_delete=models.CASCADE)
    text = models.CharField(max_length=255, null=True, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', '-created_at']),
        ]

    def __str__(self):
        return f"Notification for {self.recipient.username}: {self.notification_type}"


class Message(models.Model):
    sender = models.ForeignKey(Profile, related_name='sent_messages', on_delete=models.CASCADE)
    recipient = models.ForeignKey(Profile, related_name='received_messages', on_delete=models.CASCADE)
    body = models.TextField(blank=True)
    image = models.ImageField(upload_to='messages/', null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    is_read = models.BooleanField(default=False)
    seen_at = models.DateTimeField(null=True, blank=True)
    is_edited = models.BooleanField(default=False)
    is_deleted_by_sender = models.BooleanField(default=False)
    is_deleted_by_recipient = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['sender', 'recipient', '-created_at']),
        ]

    def __str__(self):
        return f"Message from {self.sender} to {self.recipient} at {self.created_at}"


class Report(models.Model):
    REPORT_REASONS = (
        ('spam', 'Spam'),
        ('harassment', 'Harassment'),
        ('hate_speech', 'Hate Speech'),
        ('violence', 'Violence'),
        ('nudity', 'Nudity'),
        ('other', 'Other'),
    )

    reporter = models.ForeignKey(Profile, related_name='reports_made', on_delete=models.CASCADE)
    reported_user = models.ForeignKey(Profile, related_name='reports_received', on_delete=models.CASCADE, null=True, blank=True)
    reported_post = models.ForeignKey(Post, on_delete=models.CASCADE, null=True, blank=True)
    reason = models.CharField(max_length=20, choices=REPORT_REASONS)
    description = models.TextField(null=True, blank=True)
    is_resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Report by {self.reporter.username} on {self.reported_user or self.reported_post}"


class Activity(models.Model):
    ACTIVITY_TYPES = (
        ('post', 'New Post'),
        ('follow', 'New Follow'),
        ('like', 'New Like'),
        ('comment', 'New Comment'),
        ('repost', 'New Repost'),
        ('story', 'New Story'),
        ('edit_profile', 'Profile Edit'),
        ('settings_change', 'Settings Change'),
    )

    user = models.ForeignKey(Profile, related_name='activities', on_delete=models.CASCADE)
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_TYPES)
    post = models.ForeignKey(Post, null=True, blank=True, on_delete=models.CASCADE)
    target_user = models.ForeignKey(Profile, null=True, blank=True, related_name='activity_references', on_delete=models.CASCADE)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.activity_type}"