from django.urls import path
from . import views

app_name = "chat"

urlpatterns = [
    # 1. Main index view
    path("", views.index, name="index"),
    
    # 2. API endpoint for file upload (MUST come before the dynamic path)
    path("upload_file/", views.upload_file, name="upload_file"),
    
    # 3. API endpoint for link decryption (MUST come before the dynamic path)
    path("decrypt_link/", views.decrypt_link_view, name="decrypt_link"), 
    
    # 4. Specific chat room view (This dynamic path must be last)
    path("<str:room_name>/", views.room, name="room"),
]