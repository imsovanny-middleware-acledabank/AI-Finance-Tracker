"""
URL configuration for core project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include
from django.http import HttpResponse, Http404, FileResponse
from django.conf import settings
from pathlib import Path


def app_logo(request):
    logo_path = Path(settings.BASE_DIR) / "tracker" / "templates" / "logo.jpg"
    if not logo_path.exists():
        raise Http404("Logo not found")
    return FileResponse(open(logo_path, "rb"), content_type="image/jpeg")

urlpatterns = [
    path("admin/", admin.site.urls),
    path("favicon.ico", lambda request: HttpResponse(status=204), name="favicon"),
    path("logo.jpg", app_logo, name="app_logo"),
    path("", include("tracker.urls")),
]
