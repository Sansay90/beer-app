from app.auth import passwords
from app.auth.throttle import Throttle


def test_throttle_window(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr("app.auth.throttle.time.monotonic", lambda: now[0])
    t = Throttle(2, 60)
    t.add("ip:1")
    t.add("ip:1")
    assert t.wait("ip:1") == 60
    assert t.wait("ip:2") == 0
    now[0] += 61
    assert t.wait("ip:1") == 0


def test_passwords():
    stored = passwords.hash_password("password123")
    assert stored.startswith("scrypt$") and "password123" not in stored
    assert passwords.verify_password("password123", stored)
    assert not passwords.verify_password("password124", stored)
    assert not passwords.verify_password("password123", "мусор")
