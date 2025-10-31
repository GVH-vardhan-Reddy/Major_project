from django.urls import path
from . import views
app_name = "chat"
urlpatterns = [
    path("", views.index, name="index"),
    path("<str:room_name>/", views.room, name="room"),
    path('upload/', views.upload_file, name='upload_file'),
]
