from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import (
    Profile, Post, Comment, Message, FollowersCount, FollowRequest,
    Block, Hashtag, Bookmark, Repost, Story, StoryView, Notification,
    Report, Activity, Sticker, PostSticker, CommentSticker
)
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = ['id', 'username', 'email']
        read_only_fields = ['id', 'username']


class ProfileSerializer(serializers.ModelSerializer):
    followers_count = serializers.IntegerField(read_only=True)
    following_count = serializers.IntegerField(read_only=True)
    profile_image_url = serializers.SerializerMethodField()

    class Meta:
        model = Profile
        fields = [
            'id', 'username', 'email', 'age', 'profile_image', 'profile_image_url',
            'phone_number', 'bio', 'address', 'location', 'website',
            'is_verified', 'is_private', 'is_active', 'is_staff', 'date_joined',
            'last_active', 'followers_count', 'following_count',
        ]
        read_only_fields = ['id', 'username', 'is_active', 'is_staff', 'date_joined', 'followers_count', 'following_count']
        extra_kwargs = {
            'email': {'required': True},
        }

    def get_profile_image_url(self, obj):
        request = self.context.get('request')
        if obj.profile_image and request:
            try:
                return request.build_absolute_uri(obj.profile_image.url)
            except Exception:
                return None
        return None

    def validate_username(self, value):
        if len(value) < 3:
            raise serializers.ValidationError("Username must be at least 3 characters.")
        return value

    def validate_email(self, value):
        if User.objects.filter(email=value).exclude(pk=self.instance.pk if self.instance else None).exists():
            raise serializers.ValidationError("Email is already in use.")
        return value


class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True, required=True)
    new_password = serializers.CharField(write_only=True, required=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True, required=True)

    def validate(self, data):
        user = self.context['request'].user
        if not user.check_password(data.get('current_password')):
            raise serializers.ValidationError({'current_password': 'Current password is incorrect.'})
        if data.get('new_password') != data.get('confirm_password'):
            raise serializers.ValidationError({'confirm_password': "Passwords don't match."})
        return data


class ProfileRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = Profile
        fields = ['username', 'email', 'password', 'confirm_password', 'age']

    def validate(self, data):
        if data.get('password') != data.get('confirm_password'):
            raise serializers.ValidationError("The two password fields didn't match.")
        if Profile.objects.filter(username=data.get('username')).exists():
            raise serializers.ValidationError("Username already exists.")
        if Profile.objects.filter(email=data.get('email')).exists():
            raise serializers.ValidationError("Email already exists.")
        return data

    def create(self, validated_data):
        validated_data.pop('confirm_password', None)
        password = validated_data.pop('password')
        user = Profile(**validated_data)
        user.set_password(password)
        user.save()
        return user


class StickerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sticker
        fields = ['id', 'name', 'emoji', 'image']


class PostStickerSerializer(serializers.ModelSerializer):
    sticker = StickerSerializer(read_only=True)

    class Meta:
        model = PostSticker
        fields = ['id', 'user', 'sticker', 'created_at']


class CommentStickerSerializer(serializers.ModelSerializer):
    sticker = StickerSerializer(read_only=True)

    class Meta:
        model = CommentSticker
        fields = ['id', 'user', 'sticker', 'created_at']


class CommentSerializer(serializers.ModelSerializer):
    author = ProfileSerializer(read_only=True)
    likes_count = serializers.SerializerMethodField()
    liked = serializers.SerializerMethodField()
    reactions = serializers.SerializerMethodField()
    replies = serializers.SerializerMethodField()
    is_edited = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = [
            'id', 'post', 'author', 'content', 'created_on', 'parent',
            'likes_count', 'liked', 'reactions', 'replies', 'is_edited',
        ]
        read_only_fields = ['id', 'post', 'author', 'created_on', 'likes_count', 'liked', 'reactions', 'replies', 'is_edited']

    def get_likes_count(self, obj):
        return obj.likes.count()

    def get_liked(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.likes.filter(id=request.user.id).exists()
        return False

    def get_reactions(self, obj):
        from django.db.models import Count
        sticker_counts = CommentSticker.objects.filter(comment=obj).values('sticker').annotate(count=Count('id'))
        reaction_details = []
        for reaction in sticker_counts:
            sticker_obj = Sticker.objects.get(id=reaction['sticker'])
            reaction_details.append({
                'sticker_id': sticker_obj.id,
                'name': sticker_obj.name,
                'emoji': sticker_obj.emoji,
                'count': reaction['count'],
            })
        return reaction_details

    def get_replies(self, obj):
        replies = obj.replies.all().order_by('created_on')
        return CommentSerializer(replies, many=True, context=self.context).data

    def get_is_edited(self, obj):
        return obj.updated_at and obj.updated_at > obj.created_on


class PostSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='username.username', read_only=True)
    image_url = serializers.SerializerMethodField()
    video_url = serializers.SerializerMethodField()
    total_reactions = serializers.SerializerMethodField()
    reaction_counts = serializers.SerializerMethodField()
    user_sticker = serializers.SerializerMethodField()
    user_sticker_id = serializers.SerializerMethodField()
    is_liked = serializers.SerializerMethodField()
    comments_count = serializers.SerializerMethodField()
    bookmarked = serializers.SerializerMethodField()
    repost_count = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = [
            'id', 'username', 'caption', 'created_at', 'image', 'video',
            'image_url', 'video_url',
            'is_liked', 'user_sticker', 'user_sticker_id', 'total_reactions',
            'reaction_counts', 'comments_count', 'bookmarked', 'repost_count',
            'location', 'is_repost', 'original_post', 'view_count',
        ]
        read_only_fields = ['id', 'username', 'image_url', 'video_url', 'is_liked', 'user_sticker', 'user_sticker_id', 'total_reactions', 'reaction_counts', 'comments_count', 'bookmarked', 'repost_count', 'location', 'is_repost', 'original_post', 'view_count']

    def get_image_url(self, obj):
        request = self.context.get('request')
        if obj.image and request:
            return request.build_absolute_uri(obj.image.url)
        return None

    def get_video_url(self, obj):
        request = self.context.get('request')
        if obj.video and request:
            return request.build_absolute_uri(obj.video.url)
        return None

    def get_total_reactions(self, obj):
        return obj.total_reactions

    def get_reaction_counts(self, obj):
        from django.db.models import Count
        counts = PostSticker.objects.filter(post=obj).values('sticker').annotate(count=Count('id'))
        # return map of sticker_id -> count for easy lookup
        return {str(item['sticker']): item['count'] for item in counts}

    def get_user_sticker(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            sticker = PostSticker.objects.filter(post=obj, user=request.user).first()
            return sticker.sticker.name if sticker else None
        return None

    def get_user_sticker_id(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            sticker = PostSticker.objects.filter(post=obj, user=request.user).first()
            return sticker.sticker.id if sticker else None
        return None

    def get_is_liked(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return PostSticker.objects.filter(post=obj, user=request.user).exists()
        return False

    def get_comments_count(self, obj):
        return obj.comments.filter(parent__isnull=True).count()

    def get_bookmarked(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return Bookmark.objects.filter(post=obj, user=request.user).exists()
        return False

    def get_repost_count(self, obj):
        return obj.reposts.count()


class MessageSerializer(serializers.ModelSerializer):
    sender = ProfileSerializer(read_only=True)
    recipient = ProfileSerializer(read_only=True)
    recipient = ProfileSerializer(read_only=True)
    image_url = serializers.SerializerMethodField()
    is_mine = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = [
            'id', 'sender', 'recipient', 'body', 'image_url',
            'created_at', 'is_read', 'seen_at', 'is_edited',
            'is_deleted_by_sender', 'is_deleted_by_recipient', 'is_mine',
        ]
        read_only_fields = ['id', 'sender', 'recipient', 'created_at', 'seen_at', 'is_mine']

    def get_image_url(self, obj):
        request = self.context.get('request')
        if obj.image and request:
            return request.build_absolute_uri(obj.image.url)
        return None

    def get_is_mine(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.sender_id == request.user.id
        return False


class ConversationSerializer(serializers.Serializer):
    """Lightweight per-conversation summary used in the inbox."""
    other_user = ProfileSerializer()
    last_message = MessageSerializer()
    unread_count = serializers.IntegerField()


class StorySerializer(serializers.ModelSerializer):
    user = ProfileSerializer(read_only=True)
    image_url = serializers.SerializerMethodField()
    video_url = serializers.SerializerMethodField()
    is_expired = serializers.SerializerMethodField()

    class Meta:
        model = Story
        fields = [
            'id', 'user', 'caption', 'created_at', 'expires_at',
            'image_url', 'video_url', 'is_expired', 'is_viewed',
        ]
        read_only_fields = ['id', 'user', 'created_at', 'expires_at', 'is_expired']

    def get_image_url(self, obj):
        request = self.context.get('request')
        if obj.image and request:
            return request.build_absolute_uri(obj.image.url)
        return None

    def get_video_url(self, obj):
        request = self.context.get('request')
        if obj.video and request:
            return request.build_absolute_uri(obj.video.url)
        return None

    def get_is_expired(self, obj):
        return obj.is_expired()


class NotificationSerializer(serializers.ModelSerializer):
    sender = ProfileSerializer(read_only=True)
    post = serializers.SerializerMethodField()
    comment = serializers.SerializerMethodField()
    message = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            'id', 'recipient', 'sender', 'notification_type', 'post', 'comment',
            'message', 'story', 'text', 'is_read', 'created_at',
        ]
        read_only_fields = ['id', 'recipient', 'created_at']

    def get_post(self, obj):
        if obj.post:
            return {'id': obj.post.id, 'username': obj.post.username.username, 'caption': obj.post.caption[:100]}
        return None

    def get_comment(self, obj):
        if obj.comment:
            return {'id': obj.comment.id, 'content': obj.comment.content[:100], 'post_id': obj.comment.post.id}
        return None

    def get_message(self, obj):
        if obj.message:
            return {'id': obj.message.id, 'body': obj.message.body[:100], 'sender': obj.message.sender.username}
        return None


class BookmarkSerializer(serializers.ModelSerializer):
    post = PostSerializer(read_only=True)
    user = ProfileSerializer(read_only=True)

    class Meta:
        model = Bookmark
        fields = ['id', 'user', 'post', 'created_at']
        read_only_fields = ['id', 'created_at']


class RepostSerializer(serializers.ModelSerializer):
    user = ProfileSerializer(read_only=True)
    original_post = PostSerializer(read_only=True)

    class Meta:
        model = Repost
        fields = ['id', 'user', 'original_post', 'caption', 'created_at']
        read_only_fields = ['id', 'created_at']


class FollowRequestSerializer(serializers.ModelSerializer):
    requester = ProfileSerializer(read_only=True)
    target = ProfileSerializer(read_only=True)

    class Meta:
        model = FollowRequest
        fields = ['id', 'requester', 'target', 'created_at', 'is_accepted']
        read_only_fields = ['id', 'created_at']


class BlockSerializer(serializers.ModelSerializer):
    blocker = ProfileSerializer(read_only=True)
    blocked = ProfileSerializer(read_only=True)

    class Meta:
        model = Block
        fields = ['id', 'blocker', 'blocked', 'created_at']
        read_only_fields = ['id', 'created_at']


class ReportSerializer(serializers.ModelSerializer):
    reporter = ProfileSerializer(read_only=True)
    reported_user = ProfileSerializer(read_only=True)
    reported_post = PostSerializer(read_only=True)

    class Meta:
        model = Report
        fields = [
            'id', 'reporter', 'reported_user', 'reported_post', 'reason',
            'description', 'is_resolved', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class ActivitySerializer(serializers.ModelSerializer):
    user = ProfileSerializer(read_only=True)
    target_user = ProfileSerializer(read_only=True)

    class Meta:
        model = Activity
        fields = ['id', 'user', 'activity_type', 'post', 'target_user', 'metadata', 'created_at']
        read_only_fields = ['id', 'created_at']


class HashtagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Hashtag
        fields = ['id', 'name', 'created_at', 'trending_score']
        read_only_fields = ['id', 'created_at']


class StoryViewSerializer(serializers.ModelSerializer):
    viewer = ProfileSerializer(read_only=True)

    class Meta:
        model = StoryView
        fields = ['id', 'story', 'viewer', 'viewed_at']
        read_only_fields = ['id', 'viewed_at']


class PostEditSerializer(serializers.ModelSerializer):
    """Writable serializer used for create/update of posts."""
    class Meta:
        model = Post
        fields = ['id', 'caption', 'image', 'video', 'location', 'created_at', 'is_repost', 'original_post']
        read_only_fields = ['id', 'created_at']


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        data['user'] = ProfileSerializer(self.user, context=self.context).data
        return data