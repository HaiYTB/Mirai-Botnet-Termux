# Test fixtures cho shared module
import pytest
from shared.crypto import AESCrypto

TEST_KEY = b"0" * 32  # 32 bytes for AES-256


@pytest.fixture
def crypto():
    return AESCrypto(TEST_KEY)


@pytest.fixture
def wrong_crypto():
    return AESCrypto(b"1" * 32)
