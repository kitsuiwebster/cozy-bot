import json
import os
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import logging

class DataEncryption:
    def __init__(self, password: str = None):
        """Initialize encryption with password from environment or provided"""
        if not password:
            password = os.getenv("ENCRYPTION_KEY", "DEFAULT_UNSAFE_KEY_CHANGE_THIS")
        
        # Generate key from password
        salt = b'cozybot_salt_2024'  # Fixed salt for consistency
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        self.cipher = Fernet(key)
    
    def encrypt_json(self, data: dict) -> bytes:
        """Encrypt JSON data"""
        try:
            json_str = json.dumps(data)
            encrypted_data = self.cipher.encrypt(json_str.encode())
            return encrypted_data
        except Exception as e:
            logging.error(f"❌ Encryption failed: {e}")
            raise
    
    def decrypt_json(self, encrypted_data: bytes) -> dict:
        """Decrypt JSON data"""
        try:
            decrypted_bytes = self.cipher.decrypt(encrypted_data)
            json_str = decrypted_bytes.decode()
            return json.loads(json_str)
        except Exception as e:
            logging.error(f"❌ Decryption failed: {e}")
            raise
    
    def save_encrypted_json(self, data: dict, filepath: str):
        """Save encrypted JSON to file"""
        try:
            encrypted_data = self.encrypt_json(data)
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath + '.enc', 'wb') as f:
                f.write(encrypted_data)
        except Exception as e:
            logging.error(f"❌ Failed to save encrypted data: {e}")
            raise
    
    def load_encrypted_json(self, filepath: str) -> dict:
        """Load encrypted JSON from file"""
        try:
            with open(filepath + '.enc', 'rb') as f:
                encrypted_data = f.read()
            return self.decrypt_json(encrypted_data)
        except FileNotFoundError:
            return {}
        except Exception as e:
            logging.error(f"❌ Failed to load encrypted data: {e}")
            return {}

# Global encryption instance
encryption = DataEncryption()