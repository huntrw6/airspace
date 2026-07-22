import base64
import hashlib
import json

from cryptography.fernet import Fernet, InvalidToken

from .config import Settings


def _fernet(settings: Settings) -> Fernet:
    configured = settings.push_encryption_key
    if configured:
        raw = configured.get_secret_value().encode()
        try:
            return Fernet(raw)
        except ValueError as error:
            raise ValueError("AIRSPACE_PUSH_ENCRYPTION_KEY must be a Fernet key") from error
    digest = hashlib.sha256(settings.session_pepper.get_secret_value().encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_subscription(value: dict, settings: Settings) -> dict:
    serialized = json.dumps(value, separators=(",", ":"), sort_keys=True).encode()
    return {"ciphertext": _fernet(settings).encrypt(serialized).decode()}


def decrypt_subscription(value: dict, settings: Settings) -> dict:
    # Plain objects are supported only to migrate records written by Airspace 0.1.0.
    if "ciphertext" not in value:
        return value
    try:
        decoded = _fernet(settings).decrypt(str(value["ciphertext"]).encode())
        result = json.loads(decoded)
    except (InvalidToken, ValueError, TypeError, json.JSONDecodeError) as error:
        raise ValueError("Stored push subscription cannot be decrypted") from error
    if not isinstance(result, dict):
        raise ValueError("Stored push subscription is invalid")
    return result
