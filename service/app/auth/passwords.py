"""Пароли: scrypt из стандартной библиотеки, в базе — только хэш с солью и параметрами."""
import base64
import hashlib
import hmac
import secrets

from ..errors import Invalid

PASSWORD_MIN, PASSWORD_MAX = 8, 128
SCRYPT = {"n": 2 ** 14, "r": 8, "p": 1}  # ~16 МБ и десятки миллисекунд на проверку


def _b64(b):
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _unb64(s):
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def check_password(password):
    if not PASSWORD_MIN <= len(password or "") <= PASSWORD_MAX:
        raise Invalid(f"пароль — от {PASSWORD_MIN} до {PASSWORD_MAX} символов")


def hash_password(password):
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(password.encode(), salt=salt, dklen=32, **SCRYPT)
    return f"scrypt${SCRYPT['n']}${SCRYPT['r']}${SCRYPT['p']}${_b64(salt)}${_b64(dk)}"


def verify_password(password, stored):
    try:
        algo, n, r, p, salt, dk = stored.split("$")
        expected = _unb64(dk)
        got = hashlib.scrypt(password.encode(), salt=_unb64(salt), n=int(n), r=int(r), p=int(p), dklen=len(expected))
    except (ValueError, AttributeError):
        return False
    return algo == "scrypt" and hmac.compare_digest(got, expected)


_dummy = []


def dummy_hash():
    """Хэш-пустышка: проверка пароля для несуществующей почты занимает столько же времени."""
    if not _dummy:
        _dummy.append(hash_password(secrets.token_hex(8)))
    return _dummy[0]
