from django.shortcuts import render
from django.http import JsonResponse
from better_profanity import profanity
import PyPDF2

profanity.load_censor_words()

def upload_file(request):
    if request.method == 'POST' and request.FILES.get('file'):
        uploaded_file = request.FILES['file']
        content = ""

        if uploaded_file.name.endswith('.txt'):
            content = uploaded_file.read().decode('utf-8')
        elif uploaded_file.name.endswith('.pdf'):
            reader = PyPDF2.PdfReader(uploaded_file)
            for page in reader.pages:
                content += page.extract_text() or ""

        filtered_content = profanity.censor(content)
        return JsonResponse({'filtered': filtered_content})
    return render(request, 'chat/templates/chat/room.html')

    return render(request, 'chat/room.html')
def index(request):
    return render(request, "chat/index.html")

def room(request, room_name):
    return render(request, "chat/room.html", {"room_name": room_name})
