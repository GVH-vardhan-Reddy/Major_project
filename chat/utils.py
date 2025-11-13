import base64
from cryptography.fernet import Fernet
from django.conf import settings

def get_fernet_key():
    """Derives a Fernet key from the Django SECRET_KEY."""
    # Takes the first 32 bytes of SECRET_KEY and base64 encodes it.
    key = base64.urlsafe_b64encode(settings.SECRET_KEY.encode()[:32].ljust(32, b'='))
    return key

def encrypt_link(link_url):
    """Encrypts the file URL."""
    f = Fernet(get_fernet_key())
    token = f.encrypt(link_url.encode())
    return token.decode()

def decrypt_link(encrypted_token):
    """Decrypts the token back to the file URL."""
    f = Fernet(get_fernet_key())
    try:
        link_url = f.decrypt(encrypted_token.encode())
        return link_url.decode()
    except Exception:
        # Returns None if decryption fails (e.g., tampered link)
        return None