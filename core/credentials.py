"""Encrypted credentials management."""

import json
import os
import getpass
import base64
from pathlib import Path
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from utils.logging_config import get_logger

logger = get_logger("core.credentials")

class CredentialsManager:
    """Manage encrypted database credentials."""
   
    def __init__(self, credentials_file: Path, salt_file: Path):
        self.credentials_file = credentials_file
        self.salt_file = salt_file
   
    def _generate_key(self, password: str, salt: bytes) -> Fernet:
        """Generate encryption key from password."""
        kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=100000)
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return Fernet(key)
   
    def save_credentials(self, profile: str, credentials: dict, password: str):
        """Save encrypted credentials."""
        # Generate or load salt
        if self.salt_file.exists():
            salt = self.salt_file.read_bytes()
        else:
            salt = os.urandom(16)
            self.salt_file.write_bytes(salt)
       
        fernet = self._generate_key(password, salt)
       
        # Load existing profiles
        all_profiles = {}
        if self.credentials_file.exists():
            try:
                encrypted = self.credentials_file.read_bytes()
                decrypted = fernet.decrypt(encrypted)
                all_profiles = json.loads(decrypted)
            except (json.JSONDecodeError, Exception) as e:
                # Log the error but continue - we'll create a new file
                logger.warning(f"Could not decrypt existing credentials (wrong password or corrupted file): {e}")
                logger.warning("Existing profiles will be overwritten.")
                all_profiles = {}
       
        # Add/update profile
        all_profiles[profile] = credentials
       
        # Encrypt and save
        encrypted = fernet.encrypt(json.dumps(all_profiles).encode())
        self.credentials_file.write_bytes(encrypted)
        logger.info(f"✓ Credentials saved for profile '{profile}'")
   
    def load_credentials(self, profile: str) -> dict:
        """Load and decrypt credentials."""
        if not self.credentials_file.exists() or not self.salt_file.exists():
            return None

        try:
            salt = self.salt_file.read_bytes()
            password = os.environ.get('DB_MASTER_PASSWORD')
            if not password:
                # Check if running in interactive mode (stdin is a terminal)
                import sys
                if not sys.stdin.isatty():
                    logger.error("DB_MASTER_PASSWORD environment variable not set and running in non-interactive mode")
                    return None
                password = getpass.getpass("Enter master password: ")
           
            fernet = self._generate_key(password, salt)
            encrypted = self.credentials_file.read_bytes()
            decrypted = fernet.decrypt(encrypted)
            all_profiles = json.loads(decrypted)
           
            if profile not in all_profiles:
                logger.error(f"Profile '{profile}' not found")
                return None
           
            return all_profiles[profile]
        except Exception as e:
            logger.error(f"Error loading credentials: {e}")
            return None
   
    def setup_interactive(self, profile: str):
        """Interactive credentials setup."""
        logger.info(f"=== Setup credentials for '{profile}' ===")
       
        host = input("Database host: ")
        port = input("Database port (default 3306): ") or "3306"
        database = input("Database name: ")
        user = input("Database user: ")
        password = getpass.getpass("Database password: ")
       
        credentials = {
            'host': host,
            'port': int(port),
            'database': database,
            'user': user,
            'password': password
        }
       
        logger.info("Set a master password to encrypt these credentials:")
        master_password = getpass.getpass("Master password: ")
        confirm_password = getpass.getpass("Confirm master password: ")
       
        if master_password != confirm_password:
            logger.error("Passwords don't match")
            return
       
        self.save_credentials(profile, credentials, master_password)
        logger.info("✓ Setup complete!")