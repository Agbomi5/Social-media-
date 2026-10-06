from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.files.base import ContentFile
from rest_framework.test import APIClient
from .models import Comment, FollowersCount, Notification, Post, Profile


class AuthenticationFlowTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_user_can_register_and_sign_in(self):
        registration = self.client.post(
            '/api/v1/signup/',
            {
                'username': 'newuser',
                'email': 'newuser@example.com',
                'password': 'StrongPass123!',
                'confirm_password': 'StrongPass123!',
            },
            format='json',
        )

        self.assertEqual(registration.status_code, 201)

        token_response = self.client.post(
            '/api/v1/auth/token/',
            {'username': 'newuser', 'password': 'StrongPass123!'},
            format='json',
        )

        self.assertEqual(token_response.status_code, 200)
        self.assertIn('access', token_response.data)
        self.assertIn('refresh', token_response.data)


class ProfileAndCommentFeatureTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.author = Profile.objects.create_user(
            username='commenter',
            email='commenter@example.com',
            password='StrongPass123!',
        )
        self.owner = Profile.objects.create_user(
            username='postowner',
            email='postowner@example.com',
            password='StrongPass123!',
        )
        self.mentioned = Profile.objects.create_user(
            username='mentioned',
            email='mentioned@example.com',
            password='StrongPass123!',
        )
        self.post = Post.objects.create(username=self.owner, caption='A post')

    def tearDown(self):
        self.author.refresh_from_db()
        if self.author.profile_image and self.author.profile_image.name != 'blank-profile-picture.png':
            self.author.profile_image.delete(save=False)

    def test_public_profile_includes_image_and_relationship_counts(self):
        FollowersCount.objects.create(follower=self.author.username, username=self.owner)
        FollowersCount.objects.create(follower=self.mentioned.username, username=self.owner)
        FollowersCount.objects.create(follower=self.owner.username, username=self.author)

        response = self.client.get(f'/api/v1/profile/{self.owner.username}/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['followers_count'], 2)
        self.assertEqual(response.data['following_count'], 1)
        self.assertIn('profile_image', response.data)
        self.assertIn('profile_image_url', response.data)

    def test_authenticated_user_can_update_own_profile_picture(self):
        self.client.force_authenticate(user=self.author)
        image = SimpleUploadedFile(
            'avatar.png',
            ContentFile(
                b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
                b'\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89'
                b'\x00\x00\x00\x0bIDAT\x08\xd7c\xf8\x0f\x00\x01\x01\x01'
                b'\x00\x18\xdd\x8d\xb0\x00\x00\x00\x00IEND\xaeB`\x82',
            ).read(),
            content_type='image/png',
        )

        response = self.client.patch(
            '/api/v1/profile/me/',
            {'profile_image': image},
            format='multipart',
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['profile_image'].startswith('profiles/'))
        self.assertIn('/media/profiles/', response.data['profile_image_url'])
        self.author.refresh_from_db()
        self.assertTrue(self.author.profile_image.name.startswith('profiles/'))

    def test_comment_reply_accepts_mentions_and_notifies_mentioned_user(self):
        parent = Comment.objects.create(
            post=self.post,
            author=self.owner,
            content='Original comment',
        )
        self.client.force_authenticate(user=self.author)

        response = self.client.post(
            f'/api/v1/posts/{self.post.pk}/comments/',
            {'content': 'Thanks @mentioned!', 'parent': parent.pk},
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['parent'], parent.pk)
        self.assertEqual(response.data['content'], 'Thanks @mentioned!')
        self.assertTrue(Notification.objects.filter(
            recipient=self.mentioned,
            sender=self.author,
            notification_type='mention',
            comment_id=response.data['id'],
        ).exists())

        listing = self.client.get(f'/api/v1/posts/{self.post.pk}/comments/')
        self.assertEqual(listing.status_code, 200)
        serialized_parent = listing.data['results'][0]
        self.assertEqual(serialized_parent['replies'][0]['id'], response.data['id'])

    def test_comment_reply_cannot_target_a_comment_on_another_post(self):
        other_post = Post.objects.create(username=self.owner, caption='Another post')
        foreign_comment = Comment.objects.create(
            post=other_post,
            author=self.owner,
            content='Not on this post',
        )
        self.client.force_authenticate(user=self.author)

        response = self.client.post(
            f'/api/v1/posts/{self.post.pk}/comments/',
            {'content': 'Invalid reply', 'parent': foreign_comment.pk},
            format='json',
        )

        self.assertEqual(response.status_code, 404)
