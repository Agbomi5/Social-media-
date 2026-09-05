import logging
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib import messages, auth
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.urls import NoReverseMatch
from .models import Profile, Post, FollowersCount, Message, Comment, Sticker, PostSticker, CommentSticker
from .serializers import ProfileSerializer
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.decorators import api_view, authentication_classes, permission_classes, parser_classes
from rest_framework.authentication import SessionAuthentication
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from itertools import chain
import random
from django.db.models import Q
from django.utils import timezone
from django.db.models import Count
from django.http import JsonResponse, HttpResponse
import inspect
from pygments import highlight
from pygments.lexers import PythonLexer
from pygments.formatters import HtmlFormatter



logger = logging.getLogger(__name__)


def get_request_data(request):
    return getattr(request, 'data', request.POST)


DEFAULT_REACTIONS = [
    {'name': 'Like', 'emoji': '👍'},
    {'name': 'Love', 'emoji': '❤️'},
    {'name': 'Haha', 'emoji': '😂'},
    {'name': 'Wow', 'emoji': '😮'},
    {'name': 'Sad', 'emoji': '😢'},
    {'name': 'Angry', 'emoji': '😡'},
]


def get_request_param(request, key, default=None):
    data = get_request_data(request)
    return data.get(key, default) if hasattr(data, 'get') else default


def ensure_default_stickers():
    stickers = []
    for sticker_data in DEFAULT_REACTIONS:
        sticker, _ = Sticker.objects.get_or_create(
            name=sticker_data['name'],
            defaults={'emoji': sticker_data['emoji']}
        )
        stickers.append({
            'id': sticker.id,
            'name': sticker.name,
            'emoji': sticker.emoji,
        })
    return stickers


def serialize_comment(comment, request):
    sticker_counts = CommentSticker.objects.filter(comment=comment).values('sticker').annotate(count=Count('id'))
    reaction_details = []
    for reaction in sticker_counts:
        sticker_obj = Sticker.objects.get(id=reaction['sticker'])
        reaction_details.append({
            'sticker_id': sticker_obj.id,
            'name': sticker_obj.name,
            'emoji': sticker_obj.emoji,
            'count': reaction['count'],
        })

    user_sticker = CommentSticker.objects.filter(comment=comment, user=request.user).first()
    user_liked = comment.likes.filter(id=request.user.id).exists()
    replies = [serialize_comment(reply, request) for reply in comment.replies.all().order_by('created_on')]

    return {
        'id': comment.id,
        'content': comment.content,
        'author': comment.author.username,
        'created_on': comment.created_on.isoformat(),
        'likes_count': comment.likes.count(),
        'liked': user_liked,
        'reactions': reaction_details,
        'user_sticker_id': user_sticker.sticker.id if user_sticker else None,
        'user_sticker_name': user_sticker.sticker.name if user_sticker else None,
        'replies': replies,
    }


def jwt_api_view(methods, allow_files=False):
    parser_list = [JSONParser, FormParser]
    if allow_files:
        parser_list.append(MultiPartParser)

    def decorator(func):
        decorated = parser_classes(parser_list)(func)
        decorated = permission_classes([IsAuthenticated])(decorated)
        decorated = authentication_classes([JWTAuthentication, SessionAuthentication])(decorated)
        decorated = api_view(methods)(decorated)
        return decorated

    return decorator


@jwt_api_view(['GET'])
def index(request):
    """Home page - returns user's feed or list of posts."""
    user_profile = get_object_or_404(Profile, username=request.user.username)
    
    # Get posts from users the current user follows, always include the current user's posts
    following_users = list(FollowersCount.objects.filter(follower=request.user.username).values_list('username_id', flat=True))
    # Ensure the feed always includes the current user's own posts
    if request.user.id not in following_users:
        following_users = list(following_users) + [request.user.id]

    # If there are any followed users (or self), filter to those; otherwise fallback to all posts
    if following_users:
        posts = Post.objects.filter(username_id__in=following_users).order_by('-created_at')[:50]
    else:
        posts = Post.objects.all().order_by('-created_at')[:50]
    
    posts_data = []
    for post in posts:
        user_reaction = PostSticker.objects.filter(post=post, user=request.user).first()
        image_url = None
        video_url = None
        if post.image:
            image_url = request.build_absolute_uri(post.image.url)
        if post.video:
            video_url = request.build_absolute_uri(post.video.url)
        reaction_counts = {
            str(item['sticker']): item['count']
            for item in PostSticker.objects.filter(post=post).values('sticker').annotate(count=Count('id'))
        }
        posts_data.append({
            'id': post.id,
            'username': post.username.username,
            'caption': post.caption,
            'created_at': post.created_at.isoformat(),
            'image_url': image_url,
            'video_url': video_url,
            'is_liked': user_reaction is not None,
            'user_sticker': user_reaction.sticker.name if user_reaction else None,
            'user_sticker_id': user_reaction.sticker.id if user_reaction else None,
            'total_reactions': post.total_reactions,
            'reaction_counts': reaction_counts,
        })
    
    return JsonResponse({
        'user_profile': {
            'id': user_profile.id,
            'username': user_profile.username,
            'email': user_profile.email,
            'profile_image_url': user_profile.profile_image.url if hasattr(user_profile, 'profile_image') and user_profile.profile_image else None,
        },
        'posts': posts_data
    })

#@login_required(login_url='socialmediaapp-signin')
@jwt_api_view(['GET','POST'], allow_files=True)
def upload(request):
    """Upload a new post (image or video). Requires authentication."""
    user_profile = get_object_or_404(Profile, username=request.user.username)

    if request.method == 'POST':
        media_file = request.FILES.get('media_upload')
        caption = get_request_param(request, 'caption')

        if not media_file:
            return JsonResponse({'error': 'Please select an image or video to upload'}, status=400)

        max_image_size = 10 * 1024 * 1024  # 10 MB
        max_video_size = 50 * 1024 * 1024  # 50 MB

        if media_file.content_type.startswith('image/'):
            if media_file.size > max_image_size:
                return JsonResponse({'error': 'Image file too large (max 10MB).'}, status=400)
            new_post = Post.objects.create(username=request.user, image=media_file, caption=caption)
        elif media_file.content_type.startswith('video/'):
            if media_file.size > max_video_size:
                return JsonResponse({'error': 'Video file too large (max 50MB).'}, status=400)
            new_post = Post.objects.create(username=request.user, video=media_file, caption=caption)
        else:
            return JsonResponse({'error': 'Please upload a valid image or video file'}, status=400)

        new_post.save()
        image_url = None
        video_url = None
        if new_post.image:
            image_url = request.build_absolute_uri(new_post.image.url)
        if new_post.video:
            video_url = request.build_absolute_uri(new_post.video.url)

        return JsonResponse({
            'success': True,
            'message': 'Post uploaded successfully!',
            'post': {
                'id': new_post.id,
                'username': new_post.username.username,
                'caption': new_post.caption,
                'created_at': new_post.created_at.isoformat(),
                'image_url': image_url,
                'video_url': video_url,
            }
        })

    # GET -> return user_profile info
    return JsonResponse({
        'user_profile': {
            'id': user_profile.id,
            'username': user_profile.username,
            'email': user_profile.email,
        }
    })

#@login_required(login_url='socialmediaapp-signin')
@jwt_api_view(['GET','POST'])
def search(request):
    user_profile = get_object_or_404(Profile, username=request.user.username)
    username_profile_list = []
    user_following_ids = []

    # Get profiles the user is already following
    user_following_ids = list(
        FollowersCount.objects.filter(follower=request.user.username)
        .values_list('username_id', flat=True)
    )

    if request.method == 'POST':
        query = get_request_param(request, 'username')
        if query:
            username_profile_list = Profile.objects.filter(
                Q(username__icontains=query) | Q(email__icontains=query)
            ).exclude(username=request.user.username)
        else:
            username_profile_list = Profile.objects.exclude(username=request.user.username).order_by('-date_joined')[:10]

    # Convert profiles to JSON-serializable data
    profiles_data = []
    for profile in username_profile_list:
        profiles_data.append({
            'id': profile.id,
            'username': profile.username,
            'email': profile.email,
            'bio': getattr(profile, 'bio', ''),
            'location': getattr(profile, 'location', ''),
            'is_following': profile.id in user_following_ids
        })

    return JsonResponse({
        'user_profile': {
            'id': user_profile.id,
            'username': user_profile.username,
            'email': user_profile.email,
        },
        'search_results': profiles_data,
        'user_following_ids': user_following_ids
    })


#@login_required(login_url='socialmediaapp-signin')
@jwt_api_view(['GET','POST'])
def like_post(request):
    # Handle POST requests (form submission from posts)
    if request.method == 'POST':
        post_id = get_request_param(request, 'post_id')
        action = get_request_param(request, 'action')
        username = request.user.username

        if not post_id:
            return JsonResponse({'error': 'Invalid post ID.'}, status=400)

        try:
            post = Post.objects.get(id=post_id)
        except Post.DoesNotExist:
            return JsonResponse({'error': 'Post not found.'}, status=404)

        # Handle comment addition
        if action == 'add_comment':
            comment_content = request.POST.get('comment_content', '').strip()
            if comment_content:
                comment = Comment.objects.create(
                    post=post,
                    author=request.user,
                    content=comment_content
                )
                return JsonResponse({
                    'success': True,
                    'message': 'Comment added successfully!',
                    'comment': {
                        'id': comment.id,
                        'content': comment.content,
                        'author': comment.author.username,
                        'created_on': comment.created_on.isoformat(),
                    }
                })
            else:
                return JsonResponse({'error': 'Comment cannot be empty.'}, status=400)

        # Handle reply addition
        elif action == 'add_reply':
            parent_comment_id = request.POST.get('parent_comment_id')
            reply_content = request.POST.get('reply_content', '').strip()

            if parent_comment_id and reply_content:
                try:
                    parent_comment = Comment.objects.get(id=parent_comment_id, post=post)
                    reply = Comment.objects.create(
                        post=post,
                        author=request.user,
                        content=reply_content,
                        parent=parent_comment
                    )
                    return JsonResponse({
                        'success': True,
                        'message': 'Reply added successfully!',
                        'reply': {
                            'id': reply.id,
                            'content': reply.content,
                            'author': reply.author.username,
                            'created_on': reply.created_on.isoformat(),
                            'parent_id': reply.parent.id,
                        }
                    })
                except Comment.DoesNotExist:
                    return JsonResponse({'error': 'Parent comment not found.'}, status=404)
            else:
                return JsonResponse({'error': 'Reply cannot be empty.'}, status=400)

        # Handle comment deletion
        elif action == 'delete_comment':
            comment_id = request.POST.get('comment_id')
            try:
                comment = Comment.objects.get(id=comment_id, post=post)
                if request.user == comment.author:
                    comment.delete()
                    return JsonResponse({'success': True, 'message': 'Comment deleted successfully!'})
                else:
                    return JsonResponse({'error': 'You can only delete your own comments.'}, status=403)
            except Comment.DoesNotExist:
                return JsonResponse({'error': 'Comment not found.'}, status=404)
        else:
            # Get or create default 'Like' sticker
            sticker, _ = Sticker.objects.get_or_create(name='Like', defaults={'emoji': '👍'})

            # Check existing reaction
            existing = PostSticker.objects.filter(post=post, user=request.user).first()

            if existing:
                if existing.sticker.id == sticker.id:
                    # Same sticker (Like), remove (toggle off)
                    existing.delete()
                    action_taken = 'unliked'
                else:
                    # Different sticker, replace with Like
                    existing.sticker = sticker
                    existing.created_at = timezone.now()
                    existing.save()
                    action_taken = 'liked'
            else:
                # No existing reaction, create 'Like' reaction
                PostSticker.objects.create(post=post, user=request.user, sticker=sticker)
                action_taken = 'liked'

            # Update total reaction count
            post.save()

            return JsonResponse({
                'success': True,
                'action': action_taken,
                'total_reactions': post.total_reactions
            })

    # Handle GET requests (view post detail page)
    else:
        post_id = request.GET.get('post_id')

        if not post_id:
            return JsonResponse({'error': 'Post ID required'}, status=400)

        try:
            post = Post.objects.get(id=post_id)
        except Post.DoesNotExist:
            return JsonResponse({'error': 'Post not found'}, status=404)

        # Check if current user has a reaction on this post
        user_reaction = PostSticker.objects.filter(post=post, user=request.user).first()

        stickers_data = ensure_default_stickers()
        # Get all comments (only parent comments for main display)
        comments = post.comments.filter(parent__isnull=True).order_by('-created_on')
        comments_data = [serialize_comment(comment, request) for comment in comments]

        reaction_counts = {
            str(item['sticker']): item['count']
            for item in PostSticker.objects.filter(post=post).values('sticker').annotate(count=Count('id'))
        }

        post_data = {
            'id': post.id,
            'username': post.username.username,
            'caption': post.caption,
            'created_at': post.created_at.isoformat(),
            'image_url': request.build_absolute_uri(post.image.url) if post.image else None,
            'video_url': request.build_absolute_uri(post.video.url) if post.video else None,
            'is_liked': user_reaction is not None,
            'user_sticker_id': user_reaction.sticker.id if user_reaction else None,
            'user_sticker_name': user_reaction.sticker.name if user_reaction else None,
            'total_reactions': post.total_reactions,
            'reaction_counts': reaction_counts,
        }

        return JsonResponse({
            'post': post_data,
            'comments': comments_data,
            'stickers': stickers_data
        })


#@login_required(login_url='socialmediaapp-signin')
@jwt_api_view(['POST'])
def toggle_post_like(request, pk):
    """AJAX endpoint to toggle reaction on a post."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    post = get_object_or_404(Post, pk=pk)
    user = request.user
    
    sticker_id = get_request_param(request, 'sticker_id')
    
    if sticker_id:
        try:
            sticker = Sticker.objects.get(id=sticker_id)
        except Sticker.DoesNotExist:
            return JsonResponse({'error': 'sticker not found'}, status=404)
    else:
        sticker, _ = Sticker.objects.get_or_create(name='Like', defaults={'emoji': '👍'})
    
    existing = PostSticker.objects.filter(post=post, user=user).first()
    if existing:
        if existing.sticker_id == sticker.id:
            existing.delete()
        else:
            existing.sticker = sticker
            existing.created_at = timezone.now()
            existing.save()
    else:
        PostSticker.objects.create(post=post, user=user, sticker=sticker)
    
    post.save()
    
    sticker_reactions = PostSticker.objects.filter(post=post).values('sticker').annotate(count=Count('id'))
    reaction_details = []
    counts_map = {}
    
    for reaction in sticker_reactions:
        sticker_obj = Sticker.objects.get(id=reaction['sticker'])
        counts_map[str(reaction['sticker'])] = reaction['count']
        reaction_details.append({
            'sticker_id': sticker_obj.id,
            'name': sticker_obj.name,
            'emoji': sticker_obj.emoji,
            'image': sticker_obj.image.url if sticker_obj.image else None,
            'count': reaction['count']
        })
    
    user_sticker = PostSticker.objects.filter(post=post, user=user).first()
    user_sticker_data = None
    if user_sticker:
        user_sticker_data = {
            'sticker_id': user_sticker.sticker.id,
            'name': user_sticker.sticker.name,
            'emoji': user_sticker.sticker.emoji,
            'image': user_sticker.sticker.image.url if user_sticker.sticker.image else None,
        }
    
    return JsonResponse({
        'user_sticker': user_sticker_data,
        'counts': counts_map,
        'reactions': reaction_details,
        'total_count': post.total_reactions
    })


#@login_required(login_url='socialmediaapp-signin')
@jwt_api_view(['POST'])
def toggle_post_sticker(request, pk):
    """Toggle or change sticker reaction for a post."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    post = get_object_or_404(Post, pk=pk)
    user = request.user
    sticker_id = get_request_param(request, 'sticker_id')
    if not sticker_id:
        return JsonResponse({'error': 'sticker_id required'}, status=400)

    try:
        sticker = Sticker.objects.get(id=sticker_id)
    except Sticker.DoesNotExist:
        return JsonResponse({'error': 'sticker not found'}, status=404)

    existing = PostSticker.objects.filter(post=post, user=user).first()
    if existing:
        if existing.sticker_id == sticker.id:
            existing.delete()
        else:
            existing.sticker = sticker
            existing.created_at = timezone.now()
            existing.save()
    else:
        PostSticker.objects.create(post=post, user=user, sticker=sticker)

    counts = PostSticker.objects.filter(post=post).values('sticker').annotate(count=Count('id'))
    counts_map = {str(c['sticker']): c['count'] for c in counts}
    user_sticker = PostSticker.objects.filter(post=post, user=user).first()
    user_sticker_id = user_sticker.sticker_id if user_sticker else None

    # Build detailed reaction list for frontend convenience
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

    return JsonResponse({
        'user_sticker': user_sticker_data,
        'counts': counts_map,
        'reactions': reaction_details,
        'total_count': post.total_reactions
    })


#@login_required(login_url='socialmediaapp-signin')
@jwt_api_view(['POST'])
def toggle_comment_sticker(request, pk):
    """Toggle or change sticker reaction for a comment."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    comment = get_object_or_404(Comment, pk=pk)
    user = request.user
    sticker_id = get_request_param(request, 'sticker_id')
    if not sticker_id:
        return JsonResponse({'error': 'sticker_id required'}, status=400)

    try:
        sticker = Sticker.objects.get(id=sticker_id)
    except Sticker.DoesNotExist:
        return JsonResponse({'error': 'sticker not found'}, status=404)

    existing = CommentSticker.objects.filter(comment=comment, user=user).first()
    if existing:
        if existing.sticker_id == sticker.id:
            existing.delete()
        else:
            existing.sticker = sticker
            existing.created_at = timezone.now()
            existing.save()
    else:
        CommentSticker.objects.create(comment=comment, user=user, sticker=sticker)

    counts = CommentSticker.objects.filter(comment=comment).values('sticker').annotate(count=Count('id'))
    counts_map = {str(c['sticker']): c['count'] for c in counts}
    user_sticker = CommentSticker.objects.filter(comment=comment, user=user).first()
    user_sticker_id = user_sticker.sticker_id if user_sticker else None

    reaction_details = []
    for c in counts:
        st = Sticker.objects.get(id=c['sticker'])
        reaction_details.append({
            'sticker_id': st.id,
            'name': st.name,
            'emoji': st.emoji,
            'image': st.image.url if st.image else None,
            'count': c['count'],
        })

    user_sticker_data = None
    if user_sticker:
        user_sticker_data = {
            'sticker_id': user_sticker.sticker.id,
            'name': user_sticker.sticker.name,
            'emoji': user_sticker.sticker.emoji,
            'image': user_sticker.sticker.image.url if user_sticker.sticker.image else None,
        }

    return JsonResponse({
        'user_sticker': user_sticker_data,
        'counts': counts_map,
        'reactions': reaction_details
    })


#@login_required(login_url='socialmediaapp-signin')
@jwt_api_view(['GET'])
def profile(request, pk):
    try:
        user_object = Profile.objects.get(username=pk)
    except Profile.DoesNotExist:
        return JsonResponse({'error': 'User not found.'}, status=404)

    # get posts by profile instance
    user_posts = Post.objects.filter(username=user_object).order_by('-created_at')

    # Follow button logic
    follower = request.user.username
    is_following = FollowersCount.objects.filter(follower=follower, username=user_object).exists()
    button_text = 'Unfollow' if is_following else 'Follow'

    # Follower/Following counts for the viewed profile
    user_followers = FollowersCount.objects.filter(username=user_object).count()
    user_following = FollowersCount.objects.filter(follower=user_object.username).count()

    # Convert posts to JSON data
    posts_data = []
    for post in user_posts:
        user_reaction = PostSticker.objects.filter(post=post, user=request.user).first()
        image_url = None
        video_url = None
        if post.image:
            image_url = request.build_absolute_uri(post.image.url)
        if post.video:
            video_url = request.build_absolute_uri(post.video.url)
        reaction_counts = {
            str(item['sticker']): item['count']
            for item in PostSticker.objects.filter(post=post).values('sticker').annotate(count=Count('id'))
        }
        posts_data.append({
            'id': post.id,
            'username': post.username.username,
            'caption': post.caption,
            'created_at': post.created_at.isoformat(),
            'image_url': image_url,
            'video_url': video_url,
            'is_liked': user_reaction is not None,
            'user_sticker': user_reaction.sticker.name if user_reaction else None,
            'user_sticker_id': user_reaction.sticker.id if user_reaction else None,
            'total_reactions': post.total_reactions,
            'reaction_counts': reaction_counts,
        })

    profile_image_url = None
    if hasattr(user_object, 'profile_image') and user_object.profile_image:
        profile_image_url = request.build_absolute_uri(user_object.profile_image.url)

    return JsonResponse({
        'user_profile': {
            'id': user_object.id,
            'username': user_object.username,
            'email': user_object.email,
            'bio': getattr(user_object, 'bio', ''),
            'location': getattr(user_object, 'location', ''),
            'profile_image_url': profile_image_url,
        },
        'user_posts': posts_data,
        'user_post_length': len(posts_data),
        'button_text': button_text,
        'user_followers': user_followers,
        'user_following': user_following,
        'is_following': is_following,
        'stickers': ensure_default_stickers()
    })

#@login_required(login_url='socialmediaapp-signin')
@jwt_api_view(['GET'])
def unread_messages_count(request):
    user_profile = get_object_or_404(Profile, username=request.user.username)
    count = Message.objects.filter(recipient=user_profile, is_read=False).count()
    return JsonResponse({'unread_messages_count': count})


#@login_required(login_url='socialmediaapp-signin')
@jwt_api_view(['POST'])
def follow(request):
    if request.method == 'POST':
        user_to_follow = get_request_param(request, 'user')
        follower = request.user.username

        try:
            target_profile = Profile.objects.get(username=user_to_follow)
        except Profile.DoesNotExist:
            return JsonResponse({'error': 'User to follow not found.'}, status=404)

        if FollowersCount.objects.filter(follower=follower, username=target_profile).exists():
            FollowersCount.objects.filter(follower=follower, username=target_profile).delete()
            return JsonResponse({
                'success': True,
                'message': f'Unfollowed {user_to_follow}.',
                'action': 'unfollowed',
                'is_following': False
            })
        else:
            if follower != user_to_follow:
                FollowersCount.objects.create(follower=follower, username=target_profile)
                return JsonResponse({
                    'success': True,
                    'message': f'Now following {user_to_follow}!',
                    'action': 'followed',
                    'is_following': True
                })
            else:
                return JsonResponse({'error': 'You cannot follow yourself.'}, status=400)

    else:
        return JsonResponse({'error': 'POST method required'}, status=405)
    

#@login_required(login_url='socialmediaapp-signin')
@jwt_api_view(['GET','POST'], allow_files=True)
def settings(request):
    user_profile = get_object_or_404(Profile, username=request.user.username)

    if request.method == 'POST':
        bio = get_request_param(request, 'bio')
        address = get_request_param(request, 'address')
        image = request.FILES.get('image')

        if bio is not None:
            user_profile.bio = bio
        if address is not None:
            user_profile.address = address
        if image:
            user_profile.profile_image = image

        user_profile.save()
        profile_image_url = None
        if hasattr(user_profile, 'profile_image') and user_profile.profile_image:
            profile_image_url = request.build_absolute_uri(user_profile.profile_image.url)

        return JsonResponse({
            'success': True,
            'message': 'Profile settings saved successfully!',
            'user_profile': {
                'id': user_profile.id,
                'username': user_profile.username,
                'email': user_profile.email,
                'bio': getattr(user_profile, 'bio', ''),
                'address': getattr(user_profile, 'address', ''),
                'profile_image_url': profile_image_url,
            }
        })

    # GET request - return current settings
    return JsonResponse({
        'user_profile': {
            'id': user_profile.id,
            'username': user_profile.username,
            'email': user_profile.email,
            'bio': getattr(user_profile, 'bio', ''),
            'address': getattr(user_profile, 'address', ''),
            'profile_image_url': user_profile.profile_image.url if hasattr(user_profile, 'profile_image') and user_profile.profile_image else None,
        }
    })


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

signup = csrf_exempt(SignupView.as_view())


def signin(request):
    if request.user.is_authenticated:
        return JsonResponse({'error': 'Already authenticated'}, status=400)

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

signin = csrf_exempt(signin)

#@login_required(login_url='socialmediaapp-signin')
@jwt_api_view(['POST'])
def logout(request):
    auth.logout(request)
    return JsonResponse({'success': True, 'message': 'You have been logged out.'})


#@login_required(login_url='socialmediaapp-signin')
@jwt_api_view(['GET'])
def messages_view(request):
    user_profile = get_object_or_404(Profile, username=request.user.username)

    msgs = Message.objects.filter(Q(sender=user_profile) | Q(recipient=user_profile)).order_by('-created_at')

    threads = []
    seen_partner_ids = set()

    for msg in msgs:
        other = msg.sender if msg.sender != user_profile else msg.recipient
        if other.id in seen_partner_ids:
            continue
        unread_count = Message.objects.filter(sender=other, recipient=user_profile, is_read=False).count()
        threads.append({
            'other': {
                'id': other.id,
                'username': other.username,
                'email': other.email,
            },
            'last_msg': {
                'id': msg.id,
                'body': msg.body,
                'created_at': msg.created_at.isoformat(),
                'sender': msg.sender.username,
            } if msg else None,
            'unread_count': unread_count
        })
        seen_partner_ids.add(other.id)

    try:
        followed = FollowersCount.objects.filter(follower=user_profile.username).select_related('username')
        for f in followed:
            target = f.username
            if target.id in seen_partner_ids:
                continue
            threads.append({
                'other': {
                    'id': target.id,
                    'username': target.username,
                    'email': target.email,
                },
                'last_msg': None,
                'unread_count': 0
            })
            seen_partner_ids.add(target.id)
    except Exception:
        logger.exception("Failed to include followed users in inbox for %s", user_profile.username)

    def _thread_sort_key(t):
        if t['last_msg']:
            try:
                return t['last_msg']['created_at']
            except Exception:
                return '0'
        return '0'

    threads.sort(key=_thread_sort_key, reverse=True)

    return JsonResponse({
        'user_profile': {
            'id': user_profile.id,
            'username': user_profile.username,
            'email': user_profile.email,
        },
        'conversation_list': threads,
    })


#@login_required(login_url='socialmediaapp-signin')
@jwt_api_view(['GET','POST'], allow_files=True)
def conversation_detail(request, username):
    """Show full conversation thread with a specific user."""
    current_user = get_object_or_404(Profile, username=request.user.username)

    try:
        other_user = Profile.objects.get(username=username)
    except Profile.DoesNotExist:
        return JsonResponse({'error': 'User not found.'}, status=404)

    if current_user.id == other_user.id:
        return JsonResponse({'error': 'You cannot message yourself.'}, status=400)

    if request.method == 'POST':
        body = get_request_param(request, 'body', '').strip()
        image_file = request.FILES.get('image')
        if not body and not image_file:
            return JsonResponse({'error': 'Message cannot be empty.'}, status=400)

        try:
            message = Message.objects.create(
                sender=current_user,
                recipient=other_user,
                body=body,
                image=image_file if image_file else None
            )
            return JsonResponse({
                'success': True,
                'message': 'Message sent!',
                'new_message': {
                    'id': message.id,
                    'body': message.body,
                    'image_url': message.image.url if message.image else None,
                    'sender': message.sender.username,
                    'recipient': message.recipient.username,
                    'created_at': message.created_at.isoformat(),
                    'is_read': message.is_read,
                }
            })
        except Exception as e:
            logger.exception("Error sending message")
            return JsonResponse({'error': 'Failed to send message.'}, status=500)

    conversation = Message.objects.filter(
        Q(sender=current_user, recipient=other_user) |
        Q(sender=other_user, recipient=current_user)
    ).order_by('created_at')

    try:
        unread_from_other = conversation.filter(sender=other_user, is_read=False)
        if unread_from_other.exists():
            unread_from_other.update(is_read=True)
    except Exception as e:
        logger.exception("Failed to mark messages as read")

    conversation_data = []
    for msg in conversation:
        conversation_data.append({
            'id': msg.id,
            'body': msg.body,
            'image_url': msg.image.url if msg.image else None,
            'sender': msg.sender.username,
            'recipient': msg.recipient.username,
            'created_at': msg.created_at.isoformat(),
            'is_read': msg.is_read,
        })

    return JsonResponse({
        'user_profile': {
            'id': current_user.id,
            'username': current_user.username,
            'email': current_user.email,
        },
        'other_user': {
            'id': other_user.id,
            'username': other_user.username,
            'email': other_user.email,
        },
        'conversation': conversation_data,
    })


#@login_required(login_url='socialmediaapp-signin')
@jwt_api_view(['GET','POST'], allow_files=True)
def send_message(request, username=None):
    """Separate send page: GET shows form (recipient optional), POST sends message."""
    sender = get_object_or_404(Profile, username=request.user.username)

    if username:
        try:
            recipient = Profile.objects.get(username=username)
        except Profile.DoesNotExist:
            return JsonResponse({'error': 'Recipient not found.'}, status=404)
    else:
        recipient = None

    if request.method == 'POST':
        recipient_username = get_request_param(request, 'recipient')
        body = get_request_param(request, 'body', '').strip()
        image_file = request.FILES.get('image')
        if not recipient_username or (not body and not image_file):
            return JsonResponse({'error': 'Please provide recipient and message content.'}, status=400)

        try:
            recipient = Profile.objects.get(username=recipient_username)
        except Profile.DoesNotExist:
            return JsonResponse({'error': 'Recipient not found.'}, status=404)

        message = Message.objects.create(
            sender=sender,
            recipient=recipient,
            body=body,
            image=image_file if image_file else None
        )
        return JsonResponse({
            'success': True,
            'message': f'Message sent to {recipient_username}.',
            'new_message': {
                'id': message.id,
                'body': message.body,
                'image_url': message.image.url if message.image else None,
                'sender': message.sender.username,
                'recipient': message.recipient.username,
                'created_at': message.created_at.isoformat(),
                'is_read': message.is_read,
            }
        })

    return JsonResponse({
        'user_profile': {
            'id': sender.id,
            'username': sender.username,
            'email': sender.email,
        },
        'recipient': {
            'id': recipient.id,
            'username': recipient.username,
            'email': recipient.email,
        } if recipient else None
    })


#@login_required(login_url='socialmediaapp-signin')
@jwt_api_view(['POST'])
def add_comment_to_post(request, pk):
    """Add a comment to a post (or reply to an existing comment)."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required'}, status=405)

    post = get_object_or_404(Post, pk=pk)

    if not getattr(request, 'user', None) or not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required.'}, status=401)

    # Robustly extract content from multiple possible request encodings
    content = get_request_param(request, 'content') or get_request_param(request, 'comment')
    parent_id = get_request_param(request, 'parent_id')

    if not content:
        # Try request.POST (form-encoded)
        try:
            content = request.POST.get('content') if hasattr(request, 'POST') else None
        except Exception:
            content = None

    if not content:
        # Try parsing raw body as JSON
        try:
            import json
            raw = request.body.decode('utf-8') if getattr(request, 'body', None) else ''
            if raw:
                parsed = json.loads(raw)
                content = parsed.get('content') or parsed.get('comment')
        except Exception:
            content = content

    if not content or not str(content).strip():
        return JsonResponse({'error': 'Comment cannot be empty.'}, status=400)

    parent_comment = None
    if parent_id:
        parent_comment = get_object_or_404(Comment, pk=parent_id, post=post)

    comment_obj = Comment.objects.create(
        post=post,
        author=request.user,
        content=content.strip(),
        parent=parent_comment
    )
    # Return the serialized comment (including reaction metadata)
    serialized = serialize_comment(comment_obj, request)
    return JsonResponse({
        'success': True,
        'message': 'Comment added successfully.',
        'comment': serialized
    })


#@login_required(login_url='socialmediaapp-signin')
@jwt_api_view(['POST'])
def comment(request, pk):
    comment = get_object_or_404(Comment, pk=pk)

    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required'}, status=405)

    is_dislike = False
    for dislike in comment.dislikes.all():
        if dislike == request.user:
            is_dislike = True
            break
    if is_dislike:
        comment.dislikes.remove(request.user)

    is_like = False
    for like in comment.likes.all():
        if like == request.user:
            is_like = True
            break
    if not is_like:
        comment.likes.add(request.user)
        action = 'liked'
    else:
        comment.likes.remove(request.user)
        action = 'unliked'

    return JsonResponse({
        'success': True,
        'action': action,
        'likes_count': comment.likes.count(),
        'dislikes_count': comment.dislikes.count()
    })


#@login_required(login_url='socialmediaapp-signin')
@jwt_api_view(['GET','POST'], allow_files=True)
def edit_post(request, pk):
    try:
        post = Post.objects.get(id=pk)
    except Post.DoesNotExist:
        return JsonResponse({'error': 'Post not found.'}, status=404)

    if post.username != request.user:
        return JsonResponse({'error': 'You do not have permission to edit this post.'}, status=403)

    if request.method == 'POST':
        caption = get_request_param(request, 'caption')
        media_file = request.FILES.get('media_upload')

        if caption is not None:
            post.caption = caption

        if media_file:
            max_image_size = 10 * 1024 * 1024
            max_video_size = 50 * 1024 * 1024
            if media_file.content_type.startswith('image/'):
                if media_file.size > max_image_size:
                    return JsonResponse({'error': 'Image file too large (max 10MB).'}, status=400)
                post.image = media_file
                post.video = None
            elif media_file.content_type.startswith('video/'):
                if media_file.size > max_video_size:
                    return JsonResponse({'error': 'Video file too large (max 50MB).'}, status=400)
                post.video = media_file
                post.image = None
            else:
                return JsonResponse({'error': 'Please upload a valid image or video file'}, status=400)

        post.save()
        return JsonResponse({
            'success': True,
            'message': 'Post updated successfully.',
            'post': {
                'id': post.id,
                'username': post.username.username,
                'caption': post.caption,
                'created_at': post.created_at.isoformat(),
                'image_url': post.image.url if post.image else None,
                'video_url': post.video.url if post.video else None,
            }
        })

    return JsonResponse({
        'post': {
            'id': post.id,
            'username': post.username.username,
            'caption': post.caption,
            'created_at': post.created_at.isoformat(),
            'image_url': post.image.url if post.image else None,
            'video_url': post.video.url if post.video else None,
        },
        'user_profile': {
            'id': request.user.id,
            'username': request.user.username,
            'email': request.user.email,
        }
    })


#@login_required(login_url='socialmediaapp-signin')
@jwt_api_view(['GET','POST'])
def delete_post(request, pk):
    try:
        post = Post.objects.get(id=pk)
    except Post.DoesNotExist:
        return JsonResponse({'error': 'Post not found.'}, status=404)

    if post.username != request.user:
        return JsonResponse({'error': 'You do not have permission to delete this post.'}, status=403)

    if request.method == 'POST':
        post.delete()
        return JsonResponse({
            'success': True,
            'message': 'Post deleted successfully.'
        })

    return JsonResponse({
        'post': {
            'id': post.id,
            'username': post.username.username,
            'caption': post.caption,
            'created_at': post.created_at.isoformat(),
            'image_url': post.image.url if post.image else None,
            'video_url': post.video.url if post.video else None,
        },
        'user_profile': {
            'id': request.user.id,
            'username': request.user.username,
            'email': request.user.email,
        },
        'confirmation_required': True
    })


#@login_required(login_url='socialmediaapp-signin')
@jwt_api_view(['POST'])
def toggle_comment_like(request, pk):
    """AJAX endpoint to toggle like on a comment."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    comment = get_object_or_404(Comment, pk=pk)
    user = request.user
    liked = False

    if comment.likes.filter(id=user.id).exists():
        comment.likes.remove(user)
        liked = False
    else:
        comment.likes.add(user)
        liked = True

    return JsonResponse({'liked': liked, 'likes_count': comment.likes.count()})
