"""URL configuration for the finance tracker project."""

from pathlib import Path

from django.conf import settings
from django.contrib import admin
from django.http import FileResponse, Http404, HttpResponse
from django.urls import include, path


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
