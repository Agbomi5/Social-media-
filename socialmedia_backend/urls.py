from django.contrib import admin
from django.urls import path, include, re_path
from django.http import HttpResponse
from django.shortcuts import render
from django.conf import settings
from django.conf.urls.static import static
from core import api_views


def _render_frontend_template(request, path):
    return render(request, path)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', api_views.index, name='socialmediaapp-index'),
    path('index/', api_views.index, name='index'),
    path('index.html', render, {'template_name': 'index.html'}, name='index-html'),
    path('signin.html', render, {'template_name': 'signin.html'}, name='signin-html'),
    path('signup.html', render, {'template_name': 'signup.html'}, name='signup-html'),
    path('messages.html', render, {'template_name': 'messages.html'}, name='messages-html'),
    path('api/v1/', include('core.api_urls')),
    re_path(r'^frontend/(?P<path>.*)$', _render_frontend_template),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])