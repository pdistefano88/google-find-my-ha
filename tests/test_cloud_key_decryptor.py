import pytest
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from google_find_my_ha.KeyBackup import cloud_key_decryptor
from google_find_my_ha.KeyBackup.cloud_key_decryptor import (
    decrypt_aes_cbc_no_padding,
    decrypt_aes_gcm_with_derived_key,
    derive_key_using_hkdf_sha256,
    derive_shared_secret,
)


def test_hkdf_derivation_is_deterministic_and_16_bytes():
    first = derive_key_using_hkdf_sha256(b"input", b"salt", b"info")
    second = derive_key_using_hkdf_sha256(b"input", b"salt", b"info")
    assert first == second
    assert len(first) == 16


def test_aes_gcm_encrypt_decrypt_roundtrip(monkeypatch):
    monkeypatch.setattr(cloud_key_decryptor.secrets, "token_bytes", lambda length: b"i" * length)
    key = b"k" * 16
    encrypted = cloud_key_decryptor.encrypt_aes_gcm(key, b"payload", b"aad")
    assert encrypted.startswith(b"i" * 12)
    assert cloud_key_decryptor.decrypt_aes_gcm(key, encrypted, b"aad") == b"payload"


def test_decrypt_aes_gcm_with_derived_key_rejects_bad_version():
    with pytest.raises(ValueError, match="Invalid version"):
        decrypt_aes_gcm_with_derived_key(b"\x01\x00bad", b"k" * 16, b"type")


def test_decrypt_aes_gcm_with_derived_shared_key_roundtrip(monkeypatch):
    private_key = b"shared-secret"
    key = cloud_key_decryptor.derive_key_using_hkdf_sha256(
        private_key,
        cloud_key_decryptor.SECUREBOX + cloud_key_decryptor.VERSION,
        cloud_key_decryptor.SHARED_HKDF_AES_GCM,
    )
    encrypted = cloud_key_decryptor.VERSION + cloud_key_decryptor.encrypt_aes_gcm(key, b"plain", b"type")
    assert cloud_key_decryptor.decrypt_aes_gcm_with_derived_key(encrypted, private_key, b"type") == b"plain"


def test_cbc_decrypt_roundtrip():
    key = b"k" * 16
    iv = b"i" * 16
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(b"sixteen byte msg") + encryptor.finalize()
    assert decrypt_aes_cbc_no_padding(key, iv + ciphertext) == b"sixteen byte msg"


def test_decrypt_eik_and_account_key_branch_by_length(monkeypatch):
    calls = []
    monkeypatch.setattr(cloud_key_decryptor, "decrypt_aes_cbc_no_padding", lambda key, data: calls.append(("cbc", len(data))) or b"cbc")
    monkeypatch.setattr(cloud_key_decryptor, "decrypt_aes_gcm", lambda key, data: calls.append(("gcm", len(data))) or b"gcm")

    assert cloud_key_decryptor.decrypt_eik(b"k", b"x" * 48) == b"cbc"
    assert cloud_key_decryptor.decrypt_eik(b"k", b"x" * 60) == b"gcm"
    assert cloud_key_decryptor.decrypt_account_key(b"k", b"x" * 32) == b"cbc"
    assert cloud_key_decryptor.decrypt_account_key(b"k", b"x" * 44) == b"gcm"
    with pytest.raises(ValueError, match="invalid length"):
        cloud_key_decryptor.decrypt_eik(b"k", b"x")
    with pytest.raises(ValueError, match="invalid length"):
        cloud_key_decryptor.decrypt_account_key(b"k", b"x")
    assert calls == [("cbc", 48), ("gcm", 60), ("cbc", 32), ("gcm", 44)]


def test_decrypt_simple_wrappers_delegate(monkeypatch):
    calls = []
    monkeypatch.setattr(cloud_key_decryptor, "decrypt_aes_gcm", lambda key, data: calls.append((key, data)) or b"plain")
    assert cloud_key_decryptor.decrypt_security_domain_key(b"app", b"encrypted") == b"plain"
    assert cloud_key_decryptor.decrypt_owner_key(b"shared", b"owner") == b"plain"
    assert calls == [(b"app", b"encrypted"), (b"shared", b"owner")]


def test_derive_shared_secret_matches_between_key_pairs():
    private_a = ec.generate_private_key(ec.SECP256R1(), default_backend())
    private_b = ec.generate_private_key(ec.SECP256R1(), default_backend())
    private_a_bytes = private_a.private_numbers().private_value.to_bytes(32, "big")
    public_b = private_b.public_key().public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)

    assert derive_shared_secret(private_a_bytes, public_b) == private_a.exchange(ec.ECDH(), private_b.public_key())
