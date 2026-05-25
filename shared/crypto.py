import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class AESCrypto:
    def __init__(self, key: bytes):
        if len(key) != 32:
            raise ValueError("Key phải dài đúng 32 bytes cho AES-256")
        self._aesgcm = AESGCM(key)

    def encrypt(self, plaintext: bytes) -> bytes:
        iv = os.urandom(12)
        ct = self._aesgcm.encrypt(iv, plaintext, None)
        return iv + ct

    def decrypt(self, ciphertext: bytes) -> bytes:
        if len(ciphertext) < 28:
            raise ValueError("Ciphertext quá ngắn (cần ít nhất 28 bytes: 12 IV + 16 tag)")
        iv = ciphertext[:12]
        ct = ciphertext[12:]
        return self._aesgcm.decrypt(iv, ct, None)
