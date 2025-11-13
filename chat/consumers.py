import json
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from better_profanity import profanity

# Load profanity filter once
profanity.load_censor_words()

class ChatConsumer(AsyncWebsocketConsumer):
    """
    Handles WebSocket connections for a chat room.
    """
    async def connect(self):
        # Extract room name from URL route
        self.room_name = self.scope["url_route"]["kwargs"]["room_name"]
        # Create a group name for the chat room
        self.room_group_name = "chat_%s" % self.room_name

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    # Receive message from WebSocket
    async def receive(self, text_data=None, bytes_data=None):
        """
        Receives messages directly from the connected client (browser).
        This handles standard text messages and broadcasts them to the group.
        """
        if text_data:
            text_data_json = json.loads(text_data)
            
            message = text_data_json.get("message")
            sender = text_data_json.get("sender", "AnonymousUser") # Get sender name from client

            if not message:
                return # Ignore empty messages

            # Check for profanity in the message text
            censored_message = profanity.censor(message)
            has_profanity = censored_message != message

            # Send message to room group
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    # Use 'chat_message' type for the handler function
                    'type': 'chat_message', 
                    'message': censored_message,
                    'sender': sender,
                    'profanity_warning': has_profanity, # Can be used to highlight message if needed
                }
            )

    # Receive message from room group (Handler for group_send events)
    async def chat_message(self, event):
        """
        Receives messages from the channel layer (broadcasted from
        the receive method OR the Django View's group_send).

        CRITICAL FIX: Use .get() to safely retrieve optional keys.
        """
        # Safely retrieve all relevant data using .get()
        message = event.get("message")
        encrypted_link = event.get("encrypted_link")
        
        # Determine the sender and warning status
        sender = event.get("sender", "System")
        
        # profanity_warning is sent by both client (text) and view (file)
        profanity_warning = event.get("profanity_warning", False)

        if message:
            # This is a standard text message (from client receive)
            await self.send(text_data=json.dumps({
                "type": "text",
                "sender": sender,
                "message": message,
                "profanity_warning": profanity_warning,
            }))
            
        elif encrypted_link:
            # This is a file message (sent from the Django View)
            file_name = event.get("file_name", "Unknown File")
            
            await self.send(text_data=json.dumps({
                "type": "file_upload",
                "sender": sender,
                "encrypted_link": encrypted_link,
                "file_name": file_name,
                "profanity_warning": profanity_warning,
            }))