from django.contrib import admin
from .models import (
    Profile, Post, Comment, Message, FollowersCount, FollowRequest,
    Block, Hashtag, Bookmark, Repost, Story, StoryView, Notification,
    Report, Activity, Sticker, PostSticker, CommentSticker, LikePost
)

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'is_verified', 'is_private', 'date_joined')
    search_fields = ('username', 'email')
    list_filter = ('is_verified', 'is_private', 'is_active', 'is_staff')

@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ('username', 'caption', 'created_at', 'is_repost')
    search_fields = ('caption', 'username__username')
    list_filter = ('is_repost', 'created_at')

@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('author', 'post', 'content', 'created_on')
    search_fields = ('content', 'author__username')

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('sender', 'recipient', 'body', 'created_at', 'is_read')
    search_fields = ('sender__username', 'recipient__username', 'body')
    list_filter = ('is_read',)

@admin.register(FollowRequest)
class FollowRequestAdmin(admin.ModelAdmin):
    list_display = ('requester', 'target', 'is_accepted', 'created_at')
    search_fields = ('requester__username', 'target__username')
    list_filter = ('is_accepted',)

@admin.register(Block)
class BlockAdmin(admin.ModelAdmin):
    list_display = ('blocker', 'blocked', 'created_at')
    search_fields = ('blocker__username', 'blocked__username')

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('recipient', 'sender', 'notification_type', 'is_read', 'created_at')
    search_fields = ('recipient__username', 'sender__username', 'notification_type')
    list_filter = ('notification_type', 'is_read')

@admin.register(Bookmark)
class BookmarkAdmin(admin.ModelAdmin):
    list_display = ('user', 'post', 'created_at')
    search_fields = ('user__username', 'post__id')

@admin.register(Repost)
class RepostAdmin(admin.ModelAdmin):
    list_display = ('user', 'original_post', 'created_at')
    search_fields = ('user__username', 'original_post__id')

@admin.register(Story)
class StoryAdmin(admin.ModelAdmin):
    list_display = ('user', 'caption', 'created_at', 'expires_at', 'is_viewed')
    search_fields = ('user__username', 'caption')
    list_filter = ('is_viewed',)

@admin.register(Hashtag)
class HashtagAdmin(admin.ModelAdmin):
    list_display = ('name', 'trending_score', 'created_at')
    search_fields = ('name',)

@admin.register(Sticker)
class StickerAdmin(admin.ModelAdmin):
    list_display = ('name', 'emoji')
    search_fields = ('name',)

@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ('reporter', 'reported_user', 'reported_post', 'reason', 'is_resolved', 'created_at')
    search_fields = ('reporter__username', 'reason')
    list_filter = ('reason', 'is_resolved')

@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ('user', 'activity_type', 'post', 'created_at')
    search_fields = ('user__username', 'activity_type')
    list_filter = ('activity_type',)
