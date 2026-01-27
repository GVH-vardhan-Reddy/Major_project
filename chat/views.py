import os
import json
import tempfile
import joblib
import PyPDF2
from django.shortcuts import render
from django.http import JsonResponse
from django.core.files.storage import FileSystemStorage 
from django.views.decorators.http import require_POST
from django.conf import settings
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from .utils import encrypt_link, decrypt_link

# Load the AI model once at startup
MODEL_PATH = os.path.join(settings.BASE_DIR, 'chat_filter_model.pkl')
try:
    AI_FILTER = joblib.load(MODEL_PATH)
except FileNotFoundError:
    AI_FILTER = None

fs = FileSystemStorage()

def ai_check_text(text):
    if AI_FILTER and text.strip():
        prediction = AI_FILTER.predict([text])
        return bool(prediction[0])
    return False

def index(request):
    return render(request, "chat/index.html")

def room(request, room_name):
    user_display_name = request.user.username if request.user.is_authenticated else 'AnonymousUser'
    return render(request, "chat/room.html", {
        "room_name": room_name,
        "user_display_name": user_display_name
    })

@require_POST
def upload_file(request):
    if request.method == 'POST' and request.FILES.get('file'):
        uploaded_file = request.FILES['file']
        room_name = request.POST.get('room_name') 
        sender_name = request.user.username if request.user.is_authenticated else 'AnonymousUser' 

        if not room_name:
            return JsonResponse({'error': 'Room name is missing.'}, status=400)

        # 1. Extraction
        file_extension = os.path.splitext(uploaded_file.name)[1].lower()
        content = ""

        if file_extension == '.txt':
            try:
                content = uploaded_file.read().decode('utf-8')
                uploaded_file.seek(0)
            except:
                return JsonResponse({'error': 'Invalid TXT encoding.'}, status=400)
        elif file_extension == '.pdf':
            try:
                with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
                    for chunk in uploaded_file.chunks():
                        temp_file.write(chunk)
                    temp_path = temp_file.name
                reader = PyPDF2.PdfReader(temp_path)
                for page in reader.pages:
                    content += page.extract_text() or ""
                os.remove(temp_path)
                uploaded_file.seek(0)
            except Exception as e:
                return JsonResponse({'error': f'PDF Error: {e}'}, status=400)

        # 2. AI Check
        has_profanity = ai_check_text(content) if content else False

        # 3. Save & Broadcast
        try:
            filename = fs.save(uploaded_file.name, uploaded_file)
            file_url = fs.url(filename) 
            encrypted_link = encrypt_link(file_url) #
            
            channel_layer = get_channel_layer()
            room_group_name = f'chat_{room_name}' 
            
            # Broadcast the link to the WebSocket group
            async_to_sync(channel_layer.group_send)(
                room_group_name,
                {
                    'type': 'chat_message', 
                    'message': f"Sent a file: {uploaded_file.name}",
                    'encrypted_link': encrypted_link, # This is the critical key
                    'file_name': uploaded_file.name,
                    'sender': sender_name,
                    'profanity_warning': has_profanity,
                }
            )
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
            
    return JsonResponse({'error': 'Invalid request.'}, status=400)

@require_POST
def decrypt_link_view(request):
    try:
        data = json.loads(request.body.decode('utf-8'))
        encrypted_link = data.get('encrypted_link')
        decrypted_url = decrypt_link(encrypted_link)
        return JsonResponse({'success': True, 'file_url': decrypted_url}) if decrypted_url else JsonResponse({'success': False}, status=403)
    except:
        return JsonResponse({'success': False}, status=400)