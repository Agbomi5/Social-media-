import logging
from django.db.models import Q, Count, Prefetch
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.db.models import F
from datetime import timedelta
from rest_framework import generics, status, permissions
from rest_framework.decorators import api_view, authentication_classes, permission_classes as drf_permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAuthenticatedOrReadOnly
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from rest_framework.exceptions import PermissionDenied, NotFound
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages, auth
from .models import (
    Profile, Post, Comment, Message, FollowersCount, FollowRequest,
    Block, Hashtag, Bookmark, Repost, Story, StoryView, Notification,
    Report, Activity, Sticker, PostSticker, CommentSticker
)
from .serializers import (
    ProfileSerializer, ProfileRegistrationSerializer, PostSerializer, CommentSerializer,
    MessageSerializer, StorySerializer, NotificationSerializer, BookmarkSerializer,
    RepostSerializer, FollowRequestSerializer, BlockSerializer, ReportSerializer,
    ActivitySerializer, HashtagSerializer, StickerSerializer, CustomTokenObtainPairSerializer,
    PasswordChangeSerializer, ConversationSerializer, PostEditSerializer
)
from .permission import IsOwnerOrReadOnly, IsOwner, IsOwnerProfile, IsAdminUser, IsReadOnly
from itertools import chain
import random
from django.core.cache import cache

logger = logging.getLogger(__name__)


def get_request_data(request):
    return getattr(request, 'data', request.POST)


def get_request_param(request, key, default=None):
    data = get_request_data(request)
    return data.get(key, default) if hasattr(data, 'get') else default


def build_post_context(request):
    return {'request': request}


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class FeedPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 50


# Auth views
class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


class SignupView(generics.GenericAPIView):
    serializer_class = ProfileRegistrationSerializer
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        if request.user and request.user.is_authenticated:
            return Response({'error': 'Already authenticated'}, status=status.HTTP_400_BAD_REQUEST)
        serializer = self.get_serializer()
        return Response(serializer.data)

    def post(self, request, *args, **kwargs):
        if request.user and request.user.is_authenticated:
            return Response({'error': 'Already authenticated'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response({
                'success': True,
                'message': 'Account created successfully!',
                'user': ProfileRegistrationSerializer(user).data
            }, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@csrf_exempt
def signin(request):
    if request.user.is_authenticated:
        user = request.user
        return JsonResponse({
            'success': True,
            'message': 'Already authenticated',
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
            }
        })

    if request.method == 'GET':
        return JsonResponse({'message': 'Use POST with username and password.'})

    if request.method == 'POST':
        username = request.POST.get('username') or request.GET.get('username')
        password = request.POST.get('password') or request.GET.get('password')

        if not username or not password:
            try:
                import json
                data = json.loads(request.body.decode('utf-8'))
                username = data.get('username') or username
                password = data.get('password') or password
            except Exception:
                pass

        user = auth.authenticate(request, username=username, password=password)

        if user is not None:
            auth.login(request, user)
            return JsonResponse({
                'success': True,
                'message': f'Welcome back, {user.username}!',
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                }
            })

        return JsonResponse({'error': 'Invalid username/email or password.'}, status=401)

    return JsonResponse({'error': 'POST request required with username and password'}, status=400)


def signup(request):
    return SignupView.as_view()(request)


def logout(request):
    auth.logout(request)
    return JsonResponse({'success': True, 'message': 'You have been logged out.'})


def index(request):
    return render(request, 'index.html')


# Post Views
class PostListCreateView(generics.ListCreateAPIView):
    serializer_class = PostSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        user = self.request.user if self.request.user.is_authenticated else None
        if user:
            following_users = list(FollowersCount.objects.filter(follower=user.username).values_list('username_id', flat=True))
            if user.id not in following_users:
                following_users = list(following_users) + [user.id]
            if following_users:
                return Post.objects.filter(username_id__in=following_users).select_related('username').prefetch_related('stickers').order_by('-created_at')
        return Post.objects.select_related('username').prefetch_related('stickers').order_by('-created_at')

    def perform_create(self, serializer):
        serializer.save(username=self.request.user)


class PostDetailView(generics.RetrieveAPIView):
    queryset = Post.objects.select_related('username').prefetch_related('stickers', 'comments', 'comments__author', 'stickers__sticker')
    serializer_class = PostSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]


class PostUpdateView(generics.UpdateAPIView):
    queryset = Post.objects.all()
    serializer_class = PostEditSerializer
    permission_classes = [IsOwnerOrReadOnly]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def perform_update(self, serializer):
        post = serializer.save()
        Activity.objects.create(
            user=self.request.user, activity_type='post', post=post,
            target_user=self.request.user, metadata={'action': 'edit'},
        )


class PostDeleteView(generics.DestroyAPIView):
    queryset = Post.objects.all()
    serializer_class = PostSerializer
    permission_classes = [IsOwnerOrReadOnly]


class PostLikeToggleView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PostSerializer

    def post(self, request, *args, **kwargs):
        post = get_object_or_404(Post, pk=kwargs['pk'])
        sticker_id = get_request_param(request, 'sticker_id')
        if sticker_id:
            try:
                sticker = Sticker.objects.get(id=sticker_id)
            except Sticker.DoesNotExist:
                return Response({'error': 'sticker not found'}, status=status.HTTP_404_NOT_FOUND)
        else:
            sticker, _ = Sticker.objects.get_or_create(name='Like', defaults={'emoji': '👍'})

        existing = PostSticker.objects.filter(post=post, user=request.user).first()
        action_taken = None
        if existing:
            if existing.sticker_id == sticker.id:
                existing.delete()
                action_taken = 'unliked'
            else:
                existing.sticker = sticker
                existing.created_at = timezone.now()
                existing.save()
                action_taken = 'liked'
        else:
            PostSticker.objects.create(post=post, user=request.user, sticker=sticker)
            action_taken = 'liked'
            if post.username_id != request.user.id:
                Notification.objects.create(
                    recipient=post.username,
                    sender=request.user,
                    notification_type='like',
                    post=post,
                    text=f"{request.user.username} reacted to your post",
                )
                Activity.objects.create(
                    user=request.user, activity_type='like', post=post,
                    target_user=post.username,
                    metadata={'sticker': sticker.name},
                )

        counts = PostSticker.objects.filter(post=post).values('sticker').annotate(count=Count('id'))
        counts_map = {str(c['sticker']): c['count'] for c in counts}
        reaction_details = []
        for sid, cnt in counts_map.items():
            st = Sticker.objects.get(id=int(sid))
            reaction_details.append({
                'sticker_id': st.id, 'name': st.name, 'emoji': st.emoji,
                'count': cnt,
            })
        user_sticker = PostSticker.objects.filter(post=post, user=request.user).first()
        user_sticker_data = None
        if user_sticker:
            user_sticker_data = {
                'sticker_id': user_sticker.sticker.id,
                'name': user_sticker.sticker.name,
                'emoji': user_sticker.sticker.emoji,
            }
        return Response({
            'success': True,
            'action': action_taken,
            'user_sticker': user_sticker_data,
            'counts': counts_map,
            'reactions': reaction_details,
            'total_reactions': post.total_reactions,
        })


class PostStickerToggleView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        post = get_object_or_404(Post, pk=kwargs['pk'])
        sticker_id = get_request_param(request, 'sticker_id')
        if not sticker_id:
            return Response({'error': 'sticker_id required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            sticker = Sticker.objects.get(id=sticker_id)
        except Sticker.DoesNotExist:
            return Response({'error': 'sticker not found'}, status=status.HTTP_404_NOT_FOUND)

        existing = PostSticker.objects.filter(post=post, user=request.user).first()
        if existing:
            if existing.sticker_id == sticker.id:
                existing.delete()
            else:
                existing.sticker = sticker
                existing.created_at = timezone.now()
                existing.save()
        else:
            PostSticker.objects.create(post=post, user=request.user, sticker=sticker)

        counts = PostSticker.objects.filter(post=post).values('sticker').annotate(count=Count('id'))
        counts_map = {str(c['sticker']): c['count'] for c in counts}
        user_sticker = PostSticker.objects.filter(post=post, user=request.user).first()

        reaction_details = []
        for sid, cnt in counts_map.items():
            st = Sticker.objects.get(id=int(sid))
            reaction_details.append({
                'sticker_id': st.id,
                'name': st.name,
                'emoji': st.emoji,
                'image': st.image.url if st.image else None,
                'count': cnt,
            })

        user_sticker_data = None
        if user_sticker:
            user_sticker_data = {
                'sticker_id': user_sticker.sticker.id,
                'name': user_sticker.sticker.name,
                'emoji': user_sticker.sticker.emoji,
                'image': user_sticker.sticker.image.url if user_sticker.sticker.image else None,
            }

        return Response({
            'user_sticker': user_sticker_data,
            'counts': counts_map,
            'reactions': reaction_details,
            'total_count': post.total_reactions
        })


# Comment Views
class CommentListCreateView(generics.ListCreateAPIView):
    serializer_class = CommentSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        post_id = self.kwargs.get('pk')
        return Comment.objects.filter(post_id=post_id, parent__isnull=True).select_related('author').prefetch_related('likes', 'stickers').order_by('created_on')

    def perform_create(self, serializer):
        post = get_object_or_404(Post, pk=self.kwargs.get('pk'))
        parent_id = get_request_param(self.request, 'parent')
        parent = None
        if parent_id:
            parent = get_object_or_404(Comment, pk=parent_id, post=post)
        comment = serializer.save(post=post, author=self.request.user, parent=parent)
        if post.username_id != self.request.user.id:
            Notification.objects.create(
                recipient=post.username,
                sender=self.request.user,
                notification_type='comment',
                post=post,
                comment=comment,
                text=f"{self.request.user.username} commented on your post",
            )
        if parent and parent.author_id != self.request.user.id:
            Notification.objects.create(
                recipient_id=parent.author_id,
                sender=self.request.user,
                notification_type='comment',
                post=post,
                comment=comment,
                text=f"{self.request.user.username} replied to your comment",
            )
        Activity.objects.create(
            user=self.request.user, activity_type='comment', post=post,
            target_user=post.username, metadata={'comment_id': comment.id},
        )


class CommentDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Comment.objects.select_related('author', 'post')
    serializer_class = CommentSerializer
    permission_classes = [IsAuthenticatedOrReadOnly, IsOwnerOrReadOnly]

    def perform_update(self, serializer):
        serializer.save(updated_at=timezone.now())


class CommentLikeToggleView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        comment = get_object_or_404(Comment, pk=kwargs['pk'])
        liked = False

        if comment.likes.filter(id=request.user.id).exists():
            comment.likes.remove(request.user)
        else:
            comment.likes.add(request.user)
            liked = True

        return Response({
            'liked': liked,
            'likes_count': comment.likes.count()
        })


class CommentStickerToggleView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        comment = get_object_or_404(Comment, pk=kwargs['pk'])
        sticker_id = get_request_param(request, 'sticker_id')
        if not sticker_id:
            return Response({'error': 'sticker_id required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            sticker = Sticker.objects.get(id=sticker_id)
        except Sticker.DoesNotExist:
            return Response({'error': 'sticker not found'}, status=status.HTTP_404_NOT_FOUND)

        existing = CommentSticker.objects.filter(comment=comment, user=request.user).first()
        if existing:
            if existing.sticker_id == sticker.id:
                existing.delete()
            else:
                existing.sticker = sticker
                existing.created_at = timezone.now()
                existing.save()
        else:
            CommentSticker.objects.create(comment=comment, user=request.user, sticker=sticker)

        return Response({
            'success': True,
            'reactions': CommentSticker.objects.filter(comment=comment).values('sticker').annotate(count=Count('id'))
        })


# Feed
class FeedView(generics.ListAPIView):
    serializer_class = PostSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    pagination_class = FeedPagination

    def get_queryset(self):
        user = self.request.user if self.request.user.is_authenticated else None
        if user:
            following_users = list(FollowersCount.objects.filter(follower=user.username).values_list('username_id', flat=True))
            if user.id not in following_users:
                following_users = list(following_users) + [user.id]
            if following_users:
                return Post.objects.filter(username_id__in=following_users).select_related('username').prefetch_related('stickers').order_by('-created_at')
        return Post.objects.select_related('username').prefetch_related('stickers').order_by('-created_at')

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            user_profile = None
            if request.user.is_authenticated:
                try:
                    profile = Profile.objects.get(username=request.user.username)
                    user_profile = {
                        'id': profile.id,
                        'username': profile.username,
                        'email': profile.email,
                        'profile_image_url': profile.profile_image.url if profile.profile_image else None,
                    }
                except Profile.DoesNotExist:
                    pass
            paginator = self.paginator
            return Response({
                'user_profile': user_profile,
                'posts': serializer.data,
                'next': paginator.get_next_link() if paginator else None,
                'previous': paginator.get_previous_link() if paginator else None,
                'count': paginator.page.paginator.count if paginator and hasattr(paginator, 'page') else None,
            })
        serializer = self.get_serializer(queryset, many=True)
        return Response({'posts': serializer.data})


# Search
class SearchView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        query = request.query_params.get('q', '').strip()
        if query:
            profiles = Profile.objects.filter(
                Q(username__icontains=query) | Q(email__icontains=query)
            ).exclude(username=request.user.username)[:20]
        else:
            profiles = Profile.objects.exclude(username=request.user.username).order_by('-date_joined')[:20]

        return Response({
            'results': ProfileSerializer(profiles, many=True, context={'request': request}).data
        })


# Profile
class CurrentProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = ProfileSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_object(self):
        return get_object_or_404(Profile, username=self.request.user.username)


class ProfileDetailView(generics.RetrieveAPIView):
    queryset = Profile.objects.all()
    serializer_class = ProfileSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    lookup_field = 'username'


# Follow
class FollowToggleView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        username_to_follow = kwargs['username']
        target_profile = get_object_or_404(Profile, username=username_to_follow)

        if request.user == target_profile:
            return Response({'error': 'You cannot follow yourself.'}, status=status.HTTP_400_BAD_REQUEST)

        existing = FollowersCount.objects.filter(follower=request.user.username, username=target_profile)
        if existing.exists():
            existing.delete()
            target_profile.followers_count = F('followers_count') - 1
            request.user.following_count = F('following_count') - 1
            target_profile.save(update_fields=['followers_count'])
            request.user.save(update_fields=['following_count'])
            return Response({'action': 'unfollowed', 'is_following': False})

        FollowersCount.objects.create(follower=request.user.username, username=target_profile)
        target_profile.followers_count = F('followers_count') + 1
        request.user.following_count = F('following_count') + 1
        target_profile.save(update_fields=['followers_count'])
        request.user.save(update_fields=['following_count'])
        return Response({'action': 'followed', 'is_following': True})


class FollowRequestListView(generics.ListAPIView):
    serializer_class = FollowRequestSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return FollowRequest.objects.filter(
            target=self.request.user,
            is_accepted=False
        ).select_related('requester', 'target')


class FollowRequestAcceptView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, *args, **kwargs):
        follow_request = get_object_or_404(FollowRequest, pk=pk, target=request.user)
        follow_request.is_accepted = True
        follow_request.save()
        FollowersCount.objects.get_or_create(
            follower=follow_request.requester.username,
            username=follow_request.target
        )
        Notification.objects.create(
            recipient=follow_request.requester,
            sender=follow_request.target,
            notification_type='follow',
            text=f"{follow_request.target.username} accepted your follow request"
        )
        return Response({'success': True, 'action': 'accepted'})


class FollowRequestRejectView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, *args, **kwargs):
        follow_request = get_object_or_404(FollowRequest, pk=pk, target=request.user)
        follow_request.delete()
        return Response({'success': True, 'action': 'rejected'})


class FollowerListView(generics.ListAPIView):
    serializer_class = ProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        username = self.kwargs.get('username')
        profile = get_object_or_404(Profile, username=username)
        follower_ids = FollowersCount.objects.filter(username=profile).values_list('follower', flat=True)
        return Profile.objects.filter(username__in=follower_ids)


class FollowingListView(generics.ListAPIView):
    serializer_class = ProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        username = self.kwargs.get('username')
        profile = get_object_or_404(Profile, username=username)
        following_ids = FollowersCount.objects.filter(follower=profile.username).values_list('username_id', flat=True)
        return Profile.objects.filter(id__in=following_ids)


# Block
class BlockListView(generics.ListCreateAPIView):
    serializer_class = BlockSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Block.objects.filter(blocker=self.request.user).select_related('blocker', 'blocked')

    def perform_create(self, serializer):
        serializer.save(blocker=self.request.user)


class BlockDeleteView(generics.DestroyAPIView):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Block.objects.filter(blocker=self.request.user)

    def get_object(self):
        return get_object_or_404(Block, pk=self.kwargs['pk'], blocker=self.request.user)


# Messages
class MessageListView(generics.ListAPIView):
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        user = self.request.user
        return Message.objects.filter(
            Q(sender=user) | Q(recipient=user)
        ).select_related('sender', 'recipient').order_by('-created_at')


class MessageReadView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, *args, **kwargs):
        message = get_object_or_404(Message, pk=pk, recipient=request.user)
        message.is_read = True
        message.seen_at = timezone.now()
        message.save(update_fields=['is_read', 'seen_at'])
        return Response({'success': True, 'is_read': True})


class UnreadMessageCountView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        count = Message.objects.filter(recipient=request.user, is_read=False).count()
        return Response({'unread_messages_count': count})


class ConversationListView(generics.ListAPIView):
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        user = self.request.user
        return Message.objects.filter(
            Q(sender=user) | Q(recipient=user)
        ).select_related('sender', 'recipient').order_by('-created_at')


class ConversationDetailView(generics.ListAPIView):
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        user = self.request.user
        other_username = self.kwargs['username']
        other_user = get_object_or_404(Profile, username=other_username)
        if user == other_user:
            return Message.objects.none()
        unread = Message.objects.filter(sender=other_user, recipient=user, is_read=False)
        if unread.exists():
            unread.update(is_read=True, seen_at=timezone.now())
        return Message.objects.filter(
            Q(sender=user, recipient=other_user) | Q(sender=other_user, recipient=user)
        ).select_related('sender', 'recipient').order_by('-created_at')


class ConversationListView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        user = request.user
        # Find latest message per conversation partner
        partners_qs = (
            Message.objects.filter(Q(sender=user) | Q(recipient=user))
            .values('sender_id', 'recipient_id')
            .distinct()
        )
        partner_ids = set()
        for p in partners_qs:
            other_id = p['recipient_id'] if p['sender_id'] == user.id else p['sender_id']
            if other_id != user.id:
                partner_ids.add(other_id)

        # Also include users we follow so the inbox isn't empty
        followed_ids = FollowersCount.objects.filter(follower=user.username).values_list('username_id', flat=True)
        partner_ids.update(followed_ids)
        if not partner_ids:
            return Response({'conversations': []})

        partners = Profile.objects.filter(id__in=partner_ids)
        convs = []
        for other in partners:
            qs = Message.objects.filter(
                Q(sender=user, recipient=other) | Q(sender=other, recipient=user)
            ).order_by('-created_at')
            last = qs.first()
            if not last and other not in partners.filter(id__in=followed_ids):
                continue
            unread = qs.filter(sender=other, recipient=user, is_read=False).count()
            convs.append({
                'other_user': other,
                'last_message': last,
                'unread_count': unread,
            })
        convs.sort(
            key=lambda c: c['last_message'].created_at if c['last_message'] else timezone.now(),
            reverse=True,
        )
        return Response({
            'conversations': ConversationSerializer(convs, many=True, context={'request': request}).data
        })


class ConversationMessageCreateView(generics.GenericAPIView):
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request, username, *args, **kwargs):
        sender = request.user
        recipient = get_object_or_404(Profile, username=username)
        if sender == recipient:
            return Response({'error': 'You cannot message yourself.'}, status=status.HTTP_400_BAD_REQUEST)

        body = get_request_param(request, 'body', '') or ''
        image = None
        if hasattr(request, 'FILES') and request.FILES:
            image = request.FILES.get('image')

        if not body and not image:
            return Response({'error': 'Message cannot be empty.'}, status=status.HTTP_400_BAD_REQUEST)

        msg = Message.objects.create(sender=sender, recipient=recipient, body=body, image=image if image else None)
        Notification.objects.create(
            recipient=recipient, sender=sender, notification_type='message',
            message=msg, text=f"{sender.username} sent you a message",
        )
        return Response({
            'success': True,
            'message': 'Message sent',
            'new_message': MessageSerializer(msg, context={'request': request}).data
        }, status=status.HTTP_201_CREATED)


class MessageDeleteView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk, *args, **kwargs):
        msg = get_object_or_404(Message, pk=pk)
        if msg.sender_id != request.user.id and msg.recipient_id != request.user.id:
            return Response({'error': 'Not allowed'}, status=status.HTTP_403_FORBIDDEN)
        if msg.sender_id == request.user.id:
            msg.is_deleted_by_sender = True
        else:
            msg.is_deleted_by_recipient = True
        msg.save(update_fields=['is_deleted_by_sender', 'is_deleted_by_recipient'])
        if msg.is_deleted_by_sender and msg.is_deleted_by_recipient:
            msg.delete()
        return Response({'success': True})


class MessageEditView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, *args, **kwargs):
        msg = get_object_or_404(Message, pk=pk, sender=request.user)
        body = get_request_param(request, 'body', '').strip()
        if not body:
            return Response({'error': 'Message cannot be empty.'}, status=status.HTTP_400_BAD_REQUEST)
        msg.body = body
        msg.is_edited = True
        msg.save(update_fields=['body', 'is_edited'])
        return Response({'success': True, 'message': MessageSerializer(msg, context={'request': request}).data})


class TypingIndicatorView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, username, *args, **kwargs):
        # Placeholder: real-time would need channels/websocket; this records a recent activity
        return Response({'success': True, 'is_typing': True})


class MarkConversationReadView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, username, *args, **kwargs):
        other = get_object_or_404(Profile, username=username)
        Message.objects.filter(sender=other, recipient=request.user, is_read=False).update(
            is_read=True, seen_at=timezone.now()
        )
        return Response({'success': True})


# Notifications
class NotificationListView(generics.ListAPIView):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user).select_related(
            'sender', 'recipient', 'post', 'comment', 'message', 'story'
        ).order_by('-created_at')


class NotificationMarkReadView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, *args, **kwargs):
        notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
        notification.is_read = True
        notification.save(update_fields=['is_read'])
        return Response({'success': True, 'is_read': True})


class UnreadNotificationCountView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        count = Notification.objects.filter(recipient=request.user, is_read=False).count()
        return Response({'unread_notifications_count': count})


class NotificationMarkAllReadView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
        return Response({'success': True})


# Stories
class StoryListCreateView(generics.ListCreateAPIView):
    serializer_class = StorySerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        user = self.request.user if self.request.user.is_authenticated else None
        if user:
            following_ids = FollowersCount.objects.filter(follower=user.username).values_list('username_id', flat=True)
            following_ids = list(following_ids) + [user.id]
            return Story.objects.filter(
                user_id__in=following_ids,
                expires_at__gt=timezone.now()
            ).select_related('user').order_by('-created_at')
        return Story.objects.filter(expires_at__gt=timezone.now()).select_related('user').order_by('-created_at')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class StoryDetailView(generics.RetrieveDestroyAPIView):
    queryset = Story.objects.select_related('user')
    serializer_class = StorySerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def perform_destroy(self, instance):
        if instance.user != self.request.user:
            raise PermissionDenied("You can only delete your own stories.")
        instance.delete()


class StoryViewCreateView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, *args, **kwargs):
        story = get_object_or_404(Story, pk=pk)
        StoryView.objects.get_or_create(story=story, viewer=request.user)
        return Response({'success': True})


# Bookmarks
class BookmarkListView(generics.ListAPIView):
    serializer_class = BookmarkSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        return Bookmark.objects.filter(user=self.request.user).select_related('post', 'post__username').order_by('-created_at')


class BookmarkCreateView(generics.CreateAPIView):
    serializer_class = BookmarkSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class BookmarkDeleteView(generics.DestroyAPIView):
    serializer_class = BookmarkSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Bookmark.objects.filter(user=self.request.user)

    def get_object(self):
        return get_object_or_404(Bookmark, pk=self.kwargs['pk'], user=self.request.user)


# Reposts
class RepostListCreateView(generics.ListCreateAPIView):
    serializer_class = RepostSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        return Repost.objects.filter(user=self.request.user).select_related('original_post', 'original_post__username').order_by('-created_at')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class RepostDetailView(generics.RetrieveDestroyAPIView):
    serializer_class = RepostSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Repost.objects.filter(user=self.request.user)

    def get_object(self):
        return get_object_or_404(Repost, pk=self.kwargs['pk'], user=self.request.user)


# Trending
class TrendingView(generics.ListAPIView):
    serializer_class = HashtagSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return Hashtag.objects.all().order_by('-trending_score', '-created_at')[:20]


# Suggested Users
class SuggestedUsersView(generics.ListAPIView):
    serializer_class = ProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        following_ids = FollowersCount.objects.filter(follower=user.username).values_list('username_id', flat=True)
        blocked_ids = Block.objects.filter(blocker=user).values_list('blocked_id', flat=True)
        return Profile.objects.exclude(
            id__in=list(following_ids) + list(blocked_ids) + [user.id]
        ).order_by('-date_joined')[:20]


# Reports
class ReportCreateView(generics.CreateAPIView):
    serializer_class = ReportSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(reporter=self.request.user)


# Activity
class ActivityListView(generics.ListAPIView):
    serializer_class = ActivitySerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        return Activity.objects.filter(user=self.request.user).select_related('user', 'target_user', 'post').order_by('-created_at')


# Settings
class SettingsView(generics.RetrieveUpdateAPIView):
    serializer_class = ProfileSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_object(self):
        return get_object_or_404(Profile, username=self.request.user.username)

    def perform_update(self, serializer):
        serializer.save()
        Activity.objects.create(
            user=self.request.user, activity_type='settings_change',
            target_user=self.request.user,
        )


class PasswordChangeView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PasswordChangeSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user
        user.set_password(serializer.validated_data['new_password'])
        user.save()
        return Response({'success': True, 'message': 'Password changed successfully.'})


class ProfileDetailByUsernameView(generics.RetrieveAPIView):
    serializer_class = ProfileSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    queryset = Profile.objects.all()
    lookup_field = 'username'


# Upload
class UploadView(generics.CreateAPIView):
    serializer_class = PostSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def perform_create(self, serializer):
        serializer.save(username=self.request.user)


# Stickers
class StickerListView(generics.ListAPIView):
    serializer_class = StickerSerializer
    permission_classes = [AllowAny]
    queryset = Sticker.objects.all()


class DefaultStickersView(generics.ListAPIView):
    serializer_class = StickerSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return Sticker.objects.filter(name__in=['Like', 'Love', 'Haha', 'Wow', 'Sad', 'Angry']).order_by('id')