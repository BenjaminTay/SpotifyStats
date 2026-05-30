"""Unit tests for crypto module — AES-256-GCM encrypt/decrypt (no DB)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


class TestEncryptDecrypt:
    def test_round_trip(self):
        from backend.core.crypto import decrypt, encrypt

        plaintext = "spotify-refresh-token-example-123"
        ciphertext = encrypt(plaintext)
        assert ciphertext != plaintext
        assert decrypt(ciphertext) == plaintext

    def test_round_trip_unicode(self):
        from backend.core.crypto import decrypt, encrypt

        plaintext = "测试中文Token_🎵🔐"
        ciphertext = encrypt(plaintext)
        assert decrypt(ciphertext) == plaintext

    def test_round_trip_long_string(self):
        from backend.core.crypto import decrypt, encrypt

        plaintext = "A" * 1000
        ciphertext = encrypt(plaintext)
        assert decrypt(ciphertext) == plaintext

    def test_different_ciphertexts_for_same_input(self):
        from backend.core.crypto import encrypt

        c1 = encrypt("same-token")
        c2 = encrypt("same-token")
        assert c1 != c2

    def test_decrypt_invalid_raises(self):
        from backend.core.crypto import decrypt

        with pytest.raises(Exception):
            decrypt("not-a-valid-ciphertext!!")


class TestIsEncrypted:
    def test_plain_json_detected_as_not_encrypted(self):
        """is_encrypted returns False for values starting with '{' (JSON)."""
        from backend.core.crypto import is_encrypted

        assert is_encrypted('{"access_token":"abc"}') is False

    def test_non_json_plaintext_detected_as_encrypted(self):
        """Any value not starting with '{' is considered encrypted-or-opaque."""
        from backend.core.crypto import is_encrypted

        assert is_encrypted("plain-old-token") is True

    def test_empty_string_detected_as_encrypted(self):
        from backend.core.crypto import is_encrypted

        assert is_encrypted("") is True
