from django.contrib import admin
from django.urls import path, include
# CRITICAL: Import settings and static to serve media files
from django.conf import settings 
from django.conf.urls.static import static 
urlpatterns = [
    path("admin/", admin.site.urls),
    path("chat/", include("chat.urls")),  # chat app URLs

]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)