"""
crypto.py — encrypt/decrypt the real Anthropic API key.

Usage (one-time setup):
    python crypto.py encrypt
    Enter master password: ****
    Enter Anthropic API key: sk-ant-...
    Encrypted key: gAAAAA...  (paste into .env as ANTHROPIC_API_KEY_ENCRYPTED)
"""

import os
import sys
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes


SALT_ENV = "CRYPTO_SALT"


def _get_salt() -> bytes:
    """Return salt from env, or generate and print it (first run)."""
    salt_b64 = os.getenv(SALT_ENV)
    if salt_b64:
        return base64.urlsafe_b64decode(salt_b64)
    salt = os.urandom(16)
    print(f"Generated new salt — add to .env:\n{SALT_ENV}={base64.urlsafe_b64encode(salt).decode()}")
    return salt


def _derive_fernet(password: str, salt: bytes) -> Fernet:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=480_000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    return Fernet(key)


def encrypt_key(plaintext: str, password: str, salt: bytes) -> str:
    f = _derive_fernet(password, salt)
    return f.encrypt(plaintext.encode()).decode()


def decrypt_key(ciphertext: str, password: str, salt: bytes) -> str:
    f = _derive_fernet(password, salt)
    return f.decrypt(ciphertext.encode()).decode()


def load_real_key() -> str:
    """Load and decrypt the Anthropic API key from env vars."""
    encrypted = os.getenv("ANTHROPIC_API_KEY_ENCRYPTED")
    password = os.getenv("MASTER_PASSWORD")
    salt_b64 = os.getenv(SALT_ENV)

    if not encrypted or not password or not salt_b64:
        raise RuntimeError(
            "Missing one of: ANTHROPIC_API_KEY_ENCRYPTED, MASTER_PASSWORD, CRYPTO_SALT"
        )
    salt = base64.urlsafe_b64decode(salt_b64)
    return decrypt_key(encrypted, password, salt)


# ── CLI helper ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import getpass

    cmd = sys.argv[1] if len(sys.argv) > 1 else "encrypt"

    if cmd == "encrypt":
        password = getpass.getpass("Master password: ")
        api_key = getpass.getpass("Anthropic API key: ")
        salt = _get_salt()
        encrypted = encrypt_key(api_key, password, salt)
        print(f"\nAdd to .env:\nANTHROPIC_API_KEY_ENCRYPTED={encrypted}")

    elif cmd == "verify":
        password = getpass.getpass("Master password: ")
        from dotenv import load_dotenv
        load_dotenv()
        try:
            key = load_real_key()
            print(f"OK — decrypted key starts with: {key[:12]}...")
        except Exception as e:
            print(f"ERROR: {e}")