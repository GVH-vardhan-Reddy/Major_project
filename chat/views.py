import traceback
import os
import json
import tempfile
import joblib
import PyPDF2
import pytesseract
from PIL import Image
from pdf2image import convert_from_path
from django.core.files.storage import FileSystemStorage
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.conf import settings
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import google.generativeai as genai
from .utils import encrypt_link, decrypt_link
from django.views.decorators.csrf import csrf_exempt
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
# --- SETTINGS & MODELS ---
genai.configure(api_key=settings.GOOGLE_API_KEY)
MODEL_PATH = os.path.join(settings.BASE_DIR, 'chat_filter_model.pkl')

try:
    AI_FILTER = joblib.load(MODEL_PATH)
except FileNotFoundError:
    print(f"WARNING: AI Model not found at {MODEL_PATH}")
    AI_FILTER = None

fs = FileSystemStorage()

# --- HELPER FUNCTIONS ---

def ai_check_text(text):
    if AI_FILTER and text.strip():
        prediction = AI_FILTER.predict([text])
        return bool(prediction[0])
    return False

# --- MAIN VIEWS ---

def index(request):
    """Renders the landing page."""
    return render(request, "chat/index.html")

def room(request, room_name):
    """Renders the chat room."""
    user_display_name = request.user.username if request.user.is_authenticated else 'AnonymousUser'
    return render(request, "chat/room.html", {
        "room_name": room_name,
        "user_display_name": user_display_name
    })

@csrf_exempt
def chatbot_response(request):
    """Handles Gemini AI Chatbot messages."""
    if request.method == "POST":
        try:
            model = genai.GenerativeModel("gemini-1.5-flash") # Use stable model alias
            data = json.loads(request.body)
            user_message = data.get("message")
            
            response = model.generate_content(user_message)
            return JsonResponse({"reply": response.text})
        except Exception as e:
            traceback.print_exc()
            return JsonResponse({"error": str(e)}, status=500)
    
    return render(request, "chatbot/room.html")

@csrf_exempt
def upload_file(request):
    """Handles file uploads with OCR and Profanity Filtering."""
    if request.method == 'POST':
        if not request.FILES.get('file'):
            return JsonResponse({'error': 'No file uploaded.'}, status=400)
            
        uploaded_file = request.FILES['file']
        room_name = request.POST.get('room_name') 
        sender_name = request.user.username if request.user.is_authenticated else 'AnonymousUser' 

        if not room_name:
            return JsonResponse({'error': 'Room name is missing.'}, status=400)

        file_extension = os.path.splitext(uploaded_file.name)[1].lower()
        content = ""

        try:
            # --- Text Extraction Logic ---
            if file_extension == '.txt':
                content = uploaded_file.read().decode('utf-8')
                uploaded_file.seek(0)

            elif file_extension == '.pdf':
                with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
                    for chunk in uploaded_file.chunks():
                        temp_file.write(chunk)
                    temp_path = temp_file.name
                
                # Hybrid PDF Extraction
                reader = PyPDF2.PdfReader(temp_path)
                for page in reader.pages:
                    content += page.extract_text() or ""
                POPPLER_PATH = r'C:\poppler-25.12.0\Library\bin'
                images = convert_from_path(temp_path, poppler_path=POPPLER_PATH)
                for image in images:
                    content += "\n" + pytesseract.image_to_string(image)
                
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                uploaded_file.seek(0)

            elif file_extension in ['.png', '.jpg', '.jpeg']:
                img = Image.open(uploaded_file)
                content = pytesseract.image_to_string(img)
                uploaded_file.seek(0)

        except Exception as e:
            print(f"EXTRACTION ERROR: {traceback.format_exc()}")
            return JsonResponse({'error': f'Extraction Error: {str(e)}'}, status=400)

        # AI Profanity Check
        has_profanity = ai_check_text(content) if content.strip() else False

        # Save and Broadcast
        try:
            filename = fs.save(uploaded_file.name, uploaded_file)
            file_url = fs.url(filename) 
            encrypted_link = encrypt_link(file_url)
            
            channel_layer = get_channel_layer()
            room_group_name = f'chat_{room_name}' 
            
            async_to_sync(channel_layer.group_send)(
                room_group_name,
                {
                    'type': 'chat_message', 
                    'message': f"Sent a file: {uploaded_file.name}",
                    'encrypted_link': encrypted_link,
                    'file_name': uploaded_file.name,
                    'sender': sender_name,
                    'profanity_warning': has_profanity,
                }
            )
            return JsonResponse({'success': True, 'encrypted_link': encrypted_link})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
            
    return JsonResponse({'error': 'Method not allowed.'}, status=405)

@require_POST
def decrypt_link_view(request):
    """Decrypts links for downloading."""
    try:
        data = json.loads(request.body.decode('utf-8'))
        encrypted_link = data.get('encrypted_link')
        decrypted_url = decrypt_link(encrypted_link)
        if decrypted_url:
            return JsonResponse({'success': True, 'file_url': decrypted_url})
        return JsonResponse({'success': False}, status=403)
    except:
        return JsonResponse({'success': False}, status=400)