import base64

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings
from app.core.exceptions import APEXError


def _get_fernet() -> Fernet:
    key = settings.encryption_key
    # Accept raw base64 key or pre-encoded Fernet key
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except Exception as exc:
        raise APEXError("Invalid ENCRYPTION_KEY — must be a valid Fernet key") from exc


def encrypt(plaintext: str) -> str:
    """Encrypt a string and return a base64-encoded ciphertext string."""
    fernet = _get_fernet()
    return fernet.encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    """Decrypt a previously encrypted string."""
    fernet = _get_fernet()
    try:
        return fernet.decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise APEXError("Decryption failed — token may be corrupt or key may have changed") from exc


def generate_key() -> str:
    """Generate a new Fernet key suitable for ENCRYPTION_KEY env var."""
    return Fernet.generate_key().decode()
