
from . import views
from django.urls import path, include
# CRITICAL FIX: This line MUST be present to make 'settings' available below.
from django.conf import settings 
from django.conf.urls.static import static 

app_name = "chat"

urlpatterns = [
    # 1. Main index view
    path("", views.index, name="index"),
    
    # 2. API endpoint for file upload (MUST come before the dynamic path)
    path("upload_file/", views.upload_file, name="upload_file"),
    
    # 3. API endpoint for link decryption (MUST come before the dynamic path)
    path("decrypt_link/", views.decrypt_link_view, name="decrypt_link"), 
    
    # 5. API endpoint for chatbot response
    path('ai_response/', views.chatbot_response, name='ai_response'),
    # 4. Specific chat room view (This dynamic path must be last)
    path("<str:room_name>/", views.room, name="room"),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)