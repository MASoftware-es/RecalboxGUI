from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import secrets

from .config import CLAVE_CIFRADO


_VERSION = b"v1"


def _key_stream(key: bytes, nonce: bytes, length: int) -> bytes:
    output = bytearray()
    counter = 0
    while len(output) < length:
        output.extend(hashlib.sha256(key + nonce + counter.to_bytes(4, "big")).digest())
        counter += 1
    return bytes(output[:length])


def encrypt_text(value: str) -> str:
    if not value:
        return ""
    key = hashlib.sha256(CLAVE_CIFRADO.encode("utf-8")).digest()
    nonce = secrets.token_bytes(16)
    plain = value.encode("utf-8")
    encrypted = bytes(a ^ b for a, b in zip(plain, _key_stream(key, nonce, len(plain))))
    signature = hmac.new(key, _VERSION + nonce + encrypted, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(_VERSION + nonce + signature + encrypted).decode("ascii")


def decrypt_text(value: str) -> str:
    if not value:
        return ""
    try:
        payload = base64.urlsafe_b64decode(value.encode("ascii"))
        version, nonce = payload[:2], payload[2:18]
        signature, encrypted = payload[18:50], payload[50:]
        key = hashlib.sha256(CLAVE_CIFRADO.encode("utf-8")).digest()
        expected = hmac.new(key, version + nonce + encrypted, hashlib.sha256).digest()
        if version != _VERSION or not hmac.compare_digest(signature, expected):
            return ""
        plain = bytes(a ^ b for a, b in zip(encrypted, _key_stream(key, nonce, len(encrypted))))
        return plain.decode("utf-8")
    except (binascii.Error, UnicodeDecodeError, ValueError):
        return ""
