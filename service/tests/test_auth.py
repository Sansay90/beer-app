"""Вход по почте: регистрация, письма со ссылками, новый пароль, выход, лимиты, чужой сайт, данные до входа."""
import uuid

from sqlalchemy import text

from app import db
from app.models import Recipe, User

LEGACY_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")


def test_register_validation(service):
    c = service.client()
    assert c.signup("нет-собаки")[0] == 400
    assert c.signup("a@test.local", "123")[0] == 400
    assert c.get("/auth/me")[0] == 401


def test_register_and_verify(service):
    c = service.client()
    status, me = c.signup("Owner@Test.local")
    assert status == 200 and me["email"] == "owner@test.local" and me["emailVerified"] is False
    assert me["role"] == "admin"                                   # установка у себя: первый — администратор
    assert service.client().signup("owner@test.local")[0] == 400   # почта занята

    token = service.outbox.link("verify")
    assert token
    assert c.ok("POST", "/auth/verify", {"token": token})["emailVerified"] is True
    assert c.post("/auth/verify", {"token": token})[0] == 400      # ссылка одноразовая
    assert c.ok("GET", "/auth/me")["emailVerified"] is True
    assert c.get("/auth/me")[1]["name"] == "owner"


def test_first_signup_claims_data_before_login(service, recipe):
    with db.session() as s:                                        # владелец данных, заведённых до входа
        s.add(User(id=LEGACY_ID, name="Владелец"))
        s.flush()
        s.add(Recipe(user_id=LEGACY_ID, name="Старый рецепт", data={**recipe, "name": "Старый рецепт"}))
        s.commit()
    c = service.client()
    me = c.signup("owner@test.local")[1]
    assert me["id"] == str(LEGACY_ID)
    assert [r["name"] for r in c.get("/recipes")[1]] == ["Старый рецепт"]
    other = service.client()
    assert other.signup("second@test.local")[1]["id"] != str(LEGACY_ID)
    assert other.get("/recipes")[1] == []


def add_legacy_owner():
    with db.session() as s:
        s.add(User(id=LEGACY_ID, name="Владелец"))
        s.commit()


def test_admin_emails_admin_claims_data(settings, service_factory):
    service = service_factory(settings.model_copy(update={"admin_emails": "boss@test.local"}))
    add_legacy_owner()
    me = service.client().signup("Boss@test.local")[1]
    assert me["role"] == "admin" and me["id"] == str(LEGACY_ID)
    assert service.client().signup("next@test.local")[1]["role"] == "user"


def test_admin_emails_others_do_not(settings, service_factory):
    service = service_factory(settings.model_copy(update={"admin_emails": "boss@test.local"}))
    add_legacy_owner()
    me = service.client().signup("first@test.local")[1]
    assert me["role"] == "user" and me["id"] != str(LEGACY_ID)      # данные до входа забирает только администратор


def test_reset_password(service):
    c = service.client()
    c.signup("owner@test.local", "password123")
    old = service.client()
    old.ok("POST", "/auth/login", {"email": "owner@test.local", "password": "password123"})

    assert c.post("/auth/forgot", {"email": "nobody@test.local"})[0] == 200    # ответ тот же, что и для своей
    assert service.outbox.link("reset") is None
    c.ok("POST", "/auth/forgot", {"email": "owner@test.local"})
    token = service.outbox.link("reset")
    c.ok("POST", "/auth/reset", {"token": token, "password": "newpassword1"})
    assert c.get("/auth/me")[0] == 200                              # новый пароль — сразу вход
    assert old.get("/auth/me")[0] == 401                            # прежние входы закрыты
    assert service.client().post("/auth/login", {"email": "owner@test.local", "password": "password123"})[0] == 401
    assert service.client().post("/auth/login", {"email": "owner@test.local", "password": "newpassword1"})[0] == 200
    assert c.post("/auth/reset", {"token": token, "password": "x" * 9})[0] == 400


def test_logout(service):
    c = service.client()
    c.signup("owner@test.local")
    c.ok("POST", "/auth/logout")
    assert c.get("/auth/me")[0] == 401


def test_login_throttle(service):
    service.client().signup("owner@test.local")
    codes = [service.client().post("/auth/login", {"email": "owner@test.local", "password": f"wrong{i}xx"})[0]
             for i in range(11)]
    assert codes[:10] == [401] * 10 and codes[10] == 429


def test_foreign_site(service, recipe):
    c = service.client()
    c.signup("owner@test.local")
    assert c.post("/recipes", recipe, headers={"Origin": "https://evil.example"})[0] == 403
    assert c.post("/recipes", recipe, headers={"Origin": "http://localhost:3001"})[0] == 200   # dev-сервер на этом ПК


def test_secrets_stored_hashed(service):
    service.client().signup("owner@test.local", "password123")
    with db.engine().connect() as conn:
        stored = conn.execute(text("select password_hash from users where email = 'owner@test.local'")).scalar()
        session_hash = conn.execute(text("select token_hash from sessions limit 1")).scalar()
    assert stored.startswith("scrypt$") and "password123" not in stored
    assert len(session_hash) == 64
