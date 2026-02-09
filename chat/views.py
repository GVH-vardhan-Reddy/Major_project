import traceback
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
import google.generativeai as genai
from .utils import encrypt_link, decrypt_link
from django.views.decorators.csrf import csrf_exempt
genai.configure(api_key=settings.GOOGLE_API_KEY)

@csrf_exempt
@csrf_exempt
def chatbot_response(request):
    if request.method == "POST":
        try:
            genai.configure(api_key=settings.GOOGLE_API_KEY)
            
            # Using the alias found in your terminal list
            model = genai.GenerativeModel("gemini-flash-latest")

            data = json.loads(request.body)
            user_message = data.get("message")
            
            response = model.generate_content(user_message)
            
            return JsonResponse({"reply": response.text})

        except Exception as e:
            print(f"Error during AI generation: {e}")
            traceback.print_exc()
            return JsonResponse({"error": str(e)}, status=500)
    
    return render(request, "chatbot/room.html")
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
            # Save to physical storage
            filename = fs.save(uploaded_file.name, uploaded_file)
            file_url = fs.url(filename) 
            
            # ENCRYPT the link using your helper (e.g., Fernet)
            encrypted_link = encrypt_link(file_url)
            
            # Broadcast to the room via Channels
            channel_layer = get_channel_layer()
            room_group_name = f'chat_{room_name}' 
            
            async_to_sync(channel_layer.group_send)(
                room_group_name,
                {
                    'type': 'chat_message', # Matches the handler in consumers.py
                    'message': f"Sent a file: {uploaded_file.name}",
                    'encrypted_link': encrypted_link,
                    'file_name': uploaded_file.name,
                    'sender': request.user.username if request.user.is_authenticated else 'AnonymousUser',
                    'profanity_warning': has_profanity,
                }
            )

            return JsonResponse({'success': True, 'encrypted_link': encrypted_link})
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