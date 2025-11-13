import requests
import PyPDF2
from better_profanity import profanity
from django.shortcuts import render
from django.http import JsonResponse
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.core.files.storage import FileSystemStorage 
import json
import os 
import tempfile # New import for robust temporary file handling
from .utils import encrypt_link,decrypt_link
from django.views.decorators.http import require_POST

# Initialize profanity filter once
profanity.load_censor_words()
fs = FileSystemStorage() 

# --- Index and Room Views (No Login Required) ---

def index(request):
    return render(request, "chat/index.html")

def room(request, room_name):
    # Determine the username for display, falling back to a default if anonymous
    user_display_name = request.user.username if request.user.is_authenticated else 'AnonymousUser'
    return render(request, "chat/room.html", {
        "room_name": room_name,
        "user_display_name": user_display_name # Pass the display name to the template
    })

# --- API Endpoints ---

@require_POST
def decrypt_link_view(request):
    """
    Receives an encrypted token via POST request and returns the decrypted file URL.
    """
    try:
        data = json.loads(request.body.decode('utf-8'))
        encrypted_link = data.get('encrypted_link')
        
        if not encrypted_link:
            return JsonResponse({'success': False, 'error': 'Missing encrypted token'}, status=400)
        
        decrypted_url = decrypt_link(encrypted_link)
        
        if not decrypted_url:
            return JsonResponse({'success': False, 'error': 'Invalid or expired file link.'}, status=403)
            
        return JsonResponse({'success': True, 'file_url': decrypted_url})
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON format in request body.'}, status=400)
    except Exception as e:
        print(f"Decryption error: {e}")
        return JsonResponse({'success': False, 'error': 'An internal error occurred during decryption.'}, status=500)


@require_POST
def upload_file(request):
    if request.method == 'POST' and request.FILES.get('file'):
        uploaded_file = request.FILES['file']
        room_name = request.POST.get('room_name') 
        has_profanity = False
        
        # Use a generic name if the user is not logged in
        sender_name = request.user.username if request.user.is_authenticated else 'AnonymousUser' 

        if not room_name:
            return JsonResponse({'error': 'Room name is missing.'}, status=400)

        # 1. Content Extraction and Profanity Check (Logic remains the same)
        file_extension = os.path.splitext(uploaded_file.name)[1].lower()
        content = ""
        temp_path_to_delete = None # Variable to hold the path of the temp file

        if file_extension == '.txt':
            try:
                # Read TXT content directly from the in-memory/disk-backed upload object
                content = uploaded_file.read().decode('utf-8')
                uploaded_file.seek(0)
            except UnicodeDecodeError:
                return JsonResponse({'error': 'Failed to read TXT file content (invalid encoding).'}, status=400)
                
        elif file_extension == '.pdf':
            if not PyPDF2:
                 return JsonResponse({'error': 'PDF processing library (PyPDF2) is not installed.'}, status=500)

            try:
                # Use Python's standard tempfile module for robust, cross-platform temporary file handling
                with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
                    
                    # 1. Write the uploaded file chunks to the temporary file
                    for chunk in uploaded_file.chunks():
                        temp_file.write(chunk)
                    
                    temp_path_to_delete = temp_file.name # Save path for deletion later

                # 2. Read the content from the guaranteed temporary path
                reader = PyPDF2.PdfReader(temp_path_to_delete)
                for page in reader.pages:
                    content += page.extract_text() or ""
                
                uploaded_file.seek(0) # Reset file pointer for later permanent save
                
            except Exception as e:
                # If PDF processing fails, return the error
                return JsonResponse({'error': f'Failed to process PDF content: {e}'}, status=400)
            finally:
                # 3. CRITICAL: Clean up the temporary file, even if processing failed
                if temp_path_to_delete and os.path.exists(temp_path_to_delete):
                    try:
                        os.remove(temp_path_to_delete)
                    except OSError as e:
                        # Log error but don't stop the main upload process
                        print(f"Error deleting temporary PDF file: {e}")

        
        # Apply Profanity Filter
        if content:
            has_profanity = profanity.contains_profanity(content)

        # 2. Local File Save (Original file save logic remains)
        try:
            filename = fs.save(uploaded_file.name, uploaded_file)
            file_url = fs.url(filename) 
            
        except Exception as e:
            return JsonResponse({'error': f'Failed to save file locally: {e}'}, status=500)
        
        # 3. Encrypt the Link
        encrypted_link = encrypt_link(file_url)
        
        # 4. Broadcast Encrypted Link and Warning Flag
        channel_layer = get_channel_layer()
        room_group_name = f'chat_{room_name}' 
        
        async_to_sync(channel_layer.group_send)(
            room_group_name,
            {
                'type': 'chat_message', 
                'encrypted_link': encrypted_link,
                'file_name': uploaded_file.name,
                'sender': sender_name, # <-- Use the determined sender name
                'profanity_warning': has_profanity,
            }
        )

        return JsonResponse({
            'success': True, 
            'profanity_warning': has_profanity,
            'file_url_sent': encrypted_link
        })
        
    return JsonResponse({'error': 'Invalid request or no file provided.'}, status=400)