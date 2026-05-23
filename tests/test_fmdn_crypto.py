import pytest
from ecdsa import SECP160r1

from google_find_my_ha.FMDNCrypto.eid_generator import generate_eid, get_masked_timestamp
from google_find_my_ha.FMDNCrypto.foreign_tracker_cryptor import (
    decrypt,
    decrypt_aes_eax,
    encrypt,
    encrypt_aes_eax,
    rx_to_ry,
)


def test_masked_timestamp_zeroes_rotation_bits():
    assert get_masked_timestamp(0x12345FFF, 10) == (0x12345C00).to_bytes(4, "big")


def test_generate_eid_is_deterministic_and_20_bytes():
    key = b"k" * 32
    assert generate_eid(key, 123456) == generate_eid(key, 123500)
    assert len(generate_eid(key, 123456)) == 20


def test_aes_eax_roundtrip_and_key_validation():
    ciphertext, tag = encrypt_aes_eax(b"payload", b"nonce", b"k" * 32)
    assert decrypt_aes_eax(ciphertext, tag, b"nonce", b"k" * 32) == b"payload"
    with pytest.raises(ValueError, match="Key must be 32 bytes"):
        encrypt_aes_eax(b"payload", b"nonce", b"short")
    with pytest.raises(ValueError, match="Key must be 32 bytes"):
        decrypt_aes_eax(ciphertext, tag, b"nonce", b"short")


def test_rx_to_ry_returns_even_y_for_valid_point_and_rejects_invalid():
    point = SECP160r1.generator
    y = rx_to_ry(point.x(), SECP160r1.curve)
    assert y % 2 == 0
    assert (y**2 - (point.x() ** 3 + SECP160r1.curve.a() * point.x() + SECP160r1.curve.b())) % SECP160r1.curve.p() == 0
    invalid_x = next(
        x
        for x in range(1, 100)
        if pow((x**3 + SECP160r1.curve.a() * x + SECP160r1.curve.b()) % SECP160r1.curve.p(), (SECP160r1.curve.p() - 1) // 2, SECP160r1.curve.p())
        != 1
    )
    with pytest.raises(ValueError, match="valid E2EE"):
        rx_to_ry(invalid_x, SECP160r1.curve)


def test_foreign_tracker_encrypt_decrypt_roundtrip():
    identity_key = b"i" * 32
    timestamp = 987654
    eid = generate_eid(identity_key, timestamp)
    encrypted, sx = encrypt(b"message", b"r" * 20, eid)
    assert decrypt(identity_key, encrypted, sx, timestamp) == b"message"
