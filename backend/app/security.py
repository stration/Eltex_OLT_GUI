"""Шифрование паролей через Windows DPAPI. На не-Windows — no-op base64."""
import base64
import sys

try:
    import win32crypt  # type: ignore
    HAS_DPAPI = True
except Exception:
    HAS_DPAPI = False


def encrypt(plaintext: str | None) -> bytes | None:
    if plaintext is None:
        return None
    data = plaintext.encode("utf-8")
    if HAS_DPAPI and sys.platform == "win32":
        return win32crypt.CryptProtectData(data, "LTP-GUI", None, None, None, 0)
    return b"b64:" + base64.b64encode(data)


def decrypt(blob: bytes | None) -> str | None:
    if blob is None:
        return None
    if blob.startswith(b"b64:"):
        return base64.b64decode(blob[4:]).decode("utf-8")
    if HAS_DPAPI and sys.platform == "win32":
        _, data = win32crypt.CryptUnprotectData(blob, None, None, None, 0)
        return data.decode("utf-8")
    raise RuntimeError("Не могу расшифровать пароль: нет DPAPI")