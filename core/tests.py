from django.test import TestCase
from rest_framework.test import APIClient


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
