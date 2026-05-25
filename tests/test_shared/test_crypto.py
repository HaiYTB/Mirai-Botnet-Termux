import pytest
from shared.crypto import AESCrypto


class TestAESCrypto:
    def test_key_length_validation(self):
        with pytest.raises(ValueError, match="32 bytes"):
            AESCrypto(b"short")

    def test_encrypt_decrypt_roundtrip(self, crypto):
        for plaintext in [b"hello", b"", b"x" * 1000, b"\x00\x01\x02\x03"]:
            ct = crypto.encrypt(plaintext)
            pt = crypto.decrypt(ct)
            assert pt == plaintext, f"Roundtrip failed for {plaintext!r}"

    def test_encrypt_produces_different_output(self, crypto):
        """Cùng plaintext, 2 lần encrypt phải ra ciphertext khác nhau (do IV ngẫu nhiên)."""
        ct1 = crypto.encrypt(b"hello")
        ct2 = crypto.encrypt(b"hello")
        assert ct1 != ct2

    def test_encrypt_output_format(self, crypto):
        """Output format: 12 byte IV + ciphertext + 16 byte tag"""
        ct = crypto.encrypt(b"hello world")
        assert len(ct) >= 28  # 12 IV + 16 tag minimum
        assert len(ct) == 12 + len(b"hello world") + 16

    def test_wrong_key_fails(self, crypto, wrong_crypto):
        ct = crypto.encrypt(b"secret")
        with pytest.raises(Exception):
            wrong_crypto.decrypt(ct)

    def test_tampered_ciphertext_fails(self, crypto):
        ct = crypto.encrypt(b"secret")
        # Sửa 1 byte trong ciphertext (sau IV)
        tampered = ct[:13] + bytes([ct[13] ^ 0x01]) + ct[14:]
        with pytest.raises(Exception):
            crypto.decrypt(tampered)

    def test_short_ciphertext_fails(self, crypto):
        with pytest.raises(ValueError, match="quá ngắn"):
            crypto.decrypt(b"too short")
