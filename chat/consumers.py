import json
import joblib
import os
import re
from django.conf import settings
from channels.generic.websocket import AsyncWebsocketConsumer

class ChatConsumer(AsyncWebsocketConsumer):
    AI_FILTER = None

    async def connect(self):
        if ChatConsumer.AI_FILTER is None:
            model_path = os.path.join(settings.BASE_DIR, 'chat_filter_model.pkl')
            try:
                ChatConsumer.AI_FILTER = joblib.load(model_path)
            except Exception as e:
                print(f"Error loading model: {e}")

        self.room_name = self.scope["url_route"]["kwargs"]["room_name"]
        self.room_group_name = f"chat_{self.room_name}"
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        message = data.get("message", "").strip()
        user = self.scope["user"]
        sender = user.username if user.is_authenticated else "AnonymousUser"

        is_profane = False
        if ChatConsumer.AI_FILTER and message:
            clean_text = re.sub(r'[^\w\s]', '', message).lower()
            probs = ChatConsumer.AI_FILTER.predict_proba([clean_text])
            if probs[0][1] > 0.80: 
                is_profane = True

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message', # This looks for the function below
                'message': message,
                'sender': sender,
                'profanity_warning': is_profane
            }
        )

    # --- THE MISSING HANDLER ---
    async def chat_message(self, event):
        """
        This method receives the event from group_send and 
        forwards it to the browser via the WebSocket.
        """
        # Send data to the WebSocket
        await self.send(text_data=json.dumps({
            'type': 'chat_message',
            'message': event.get('message', ''),
            'sender': event.get('sender', 'System'),
            'profanity_warning': event.get('profanity_warning', False),
            'encrypted_link': event.get('encrypted_link'), # The encrypted PDF link
            'file_name': event.get('file_name'),
        }))