from django.shortcuts import render
from django.http import JsonResponse
from better_profanity import profanity
import PyPDF2

profanity.load_censor_words()

def index(request):
    return render(request, "chat/index.html")

def room(request, room_name):
    return render(request, "chat/room.html", {"room_name": room_name})
