# my_app/chat_logic.py
import joblib
import os
from django.conf import settings

# Load model into memory once when the server starts
MODEL_PATH = os.path.join(settings.BASE_DIR, 'chat_filter_model.pkl')
FILTER_MODEL = joblib.load(MODEL_PATH)

def check_message(text):
    """
    Returns True if message is profane, False if clean.
    """
    prediction = FILTER_MODEL.predict([text])
    return bool(prediction[0])