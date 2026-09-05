from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db.models import Q

class EmailUsernameAuthBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()
        if not username or not password:
            return None

        # Prefer a single matching user; if multiple exist, pick first and log.
        qs = UserModel.objects.filter(Q(username__iexact=username) | Q(email__iexact=username)).order_by('id')
        user = qs.first()
        if user and user.check_password(password):
            return user
        return None

    def get_user(self, user_id):
        UserModel = get_user_model()
        try:
            return UserModel.objects.get(pk=user_id)
        except UserModel.DoesNotExist:
            return None