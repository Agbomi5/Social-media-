from rest_framework.permissions import BasePermission, AllowAny, IsAuthenticated as DRFIsAuthenticated
from rest_framework import generics
from .models import Profile
from .serializers import ProfileSerializer, UserSerializer


class IsAdminUser(BasePermission):
    def has_permission(self, request, view):
        user = getattr(request, 'user', None)
        return bool(user and user.is_authenticated and getattr(user, 'is_staff', False))


class IsOwnerOrReadOnly(BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return True
        if hasattr(obj, 'username'):
            return obj.username == request.user
        if hasattr(obj, 'author'):
            return obj.author == request.user
        if hasattr(obj, 'user'):
            return obj.user == request.user
        if hasattr(obj, 'sender'):
            return obj.sender == request.user
        return False


class IsOwner(BasePermission):
    def has_object_permission(self, request, view, obj):
        if hasattr(obj, 'username'):
            return obj.username == request.user
        if hasattr(obj, 'author'):
            return obj.author == request.user
        if hasattr(obj, 'user'):
            return obj.user == request.user
        return False


class IsReadOnly(BasePermission):
    def has_permission(self, request, view):
        return request.method in ['GET', 'HEAD', 'OPTIONS']


class IsOwnerProfile(BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.username == request.user