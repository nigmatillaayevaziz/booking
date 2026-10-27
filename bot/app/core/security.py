import hashlib
import hmac

from cryptography.fernet import Fernet, InvalidToken


class PIICipher:
    def __init__(self, encryption_key: str, hash_key: str) -> None:
        self._fernet = Fernet(encryption_key.encode())
        self._hash_key = hash_key.encode()

    def encrypt(self, value: str | None) -> str | None:
        if value is None:
            return None
        return self._fernet.encrypt(value.encode()).decode()

    def decrypt(self, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            return self._fernet.decrypt(value.encode()).decode()
        except InvalidToken as error:
            raise ValueError("PII qiymatini ochib bo‘lmadi") from error

    def blind_index(self, value: str) -> str:
        normalized = "".join(value.split()).lower()
        return hmac.new(self._hash_key, normalized.encode(), hashlib.sha256).hexdigest()
