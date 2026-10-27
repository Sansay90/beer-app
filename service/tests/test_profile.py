"""Профиль: ник при регистрации и его правила, смена ника, аватар, страница пивовара; почта не видна никому,
кроме самого пользователя и администратора."""
import io
import json
import urllib.request
from urllib.parse import quote

import pytest
from PIL import Image

from app.auth import profile
from app.errors import Invalid


def png(size=(800, 500)):
    out = io.BytesIO()
    Image.new("RGB", size, (90, 140, 40)).save(out, "PNG")
    return out.getvalue()


def put_avatar(client, data):
    req = urllib.request.Request(f"{client.base}/api/auth/me/avatar", data=data, method="PUT",
                                 headers={"Content-Type": "image/png"})
    try:
        with client.opener.open(req, timeout=30) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, None


def fetch(client, url):
    with client.opener.open(f"{client.base}{url}", timeout=30) as r:
        return r.status, r.headers.get("Content-Type"), r.read()


@pytest.mark.parametrize("nick", ["Пивовар_Иван", "ivan-brews", "Hop42", "ёжик"])
def test_nick_allowed(nick):
    assert profile.check_nick(f"  {nick} ") == nick


@pytest.mark.parametrize("nick", ["ab", "a" * 25, "Иван Петров", "_ivan", "Ivаn", "admin", "Админ", "ivan@mail"])
def test_nick_rejected(nick):
    with pytest.raises(Invalid):
        profile.check_nick(nick)


def test_nick_key_ignores_case_and_yo():
    assert profile.nick_key("Ёжик") == profile.nick_key("ежик") == "ежик"


def test_register_nick_optional_but_free(service):
    a, b, c = service.client(), service.client(), service.client()
    status, me = a.signup("a@test.local", name="Пивовар_Иван")
    assert status == 200 and me["name"] == "Пивовар_Иван" and me["avatar"] is None
    assert b.signup("b@test.local", name="пивовар_иван")[0] == 400           # занят без учёта регистра
    assert b.signup("b@test.local", name="x")[0] == 400                      # не по правилам
    assert b.signup("b@test.local", name="Brewer_B")[0] == 200
    status, me = c.post("/auth/register", {"email": "c@test.local", "password": "password123"})
    assert status == 200 and me["name"] is None                              # без ника — можно


def test_without_nick(service, recipe):
    c, guest = service.client(), service.client()
    c.post("/auth/register", {"email": "no.nick@test.local", "password": "password123", "name": "  "})
    c.ok("POST", "/auth/verify", {"token": service.outbox.link("verify")})
    rid = c.ok("POST", "/recipes", recipe)["id"]
    c.ok("PUT", f"/recipes/{rid}/visibility", {"visibility": "public"})
    listed = guest.ok("GET", "/recipes")
    assert listed[0]["author"]["name"] is None                               # интерфейс: «Неизвестный пивовар»
    assert "no.nick" not in json.dumps(listed)
    c.ok("PATCH", "/auth/me", {"name": "Появился"})
    assert guest.ok("GET", "/recipes")[0]["author"]["name"] == "Появился"


def test_change_nick(service):
    a, b = service.client(), service.client()
    a.signup("a@test.local", name="first")
    b.signup("b@test.local", name="second")
    assert a.request("PATCH", "/auth/me", {"name": "Second"})[0] == 400       # занят
    status, me = a.request("PATCH", "/auth/me", {"name": "Новый_ник"})
    assert status == 200 and me["name"] == "Новый_ник"
    assert a.get("/auth/me")[1]["name"] == "Новый_ник"
    assert a.request("PATCH", "/auth/me", {"name": "новый_НИК"})[0] == 200   # свой — можно сменить регистр
    assert service.client().request("PATCH", "/auth/me", {"name": "guest"})[0] == 401


def test_avatar(service):
    a = service.client()
    a.signup("a@test.local", name="with_avatar")
    assert put_avatar(a, b"not an image")[0] == 415
    status, me = put_avatar(a, png())
    assert status == 200 and me["avatar"].startswith(f"/api/avatars/{me['id']}?v=")
    status, kind, data = fetch(service.client(), me["avatar"])               # видно и гостю
    assert status == 200 and kind == "image/jpeg"
    with Image.open(io.BytesIO(data)) as im:
        assert im.size == (profile.AVATAR_SIDE, profile.AVATAR_SIDE)
    first = me["avatar"]
    me = put_avatar(a, png((300, 900)))[1]
    assert me["avatar"] != first                                              # новый — новый адрес, мимо кеша
    me = a.ok("DELETE", "/auth/me/avatar")
    assert me["avatar"] is None
    assert service.client().get(f"/avatars/{me['id']}")[0] == 404


def test_brewer_page_and_privacy(service, recipe):
    author, guest = service.client(), service.client()
    author.signup("secret.person@test.local", name="Открытый")
    author.ok("POST", "/auth/verify", {"token": service.outbox.link("verify")})
    public = author.ok("POST", "/recipes", {**recipe, "name": "Публичный"})["id"]
    author.ok("POST", "/recipes", {**recipe, "name": "Личный"})
    author.ok("PUT", f"/recipes/{public}/visibility", {"visibility": "public"})

    brewer = guest.ok("GET", f"/brewers/{quote('открытый')}")                            # ник без учёта регистра
    assert brewer["name"] == "Открытый" and brewer["recipes"] == 1 and brewer["avatar"] is None
    by_author = f"/recipes?author={quote('Открытый')}"
    assert [r["name"] for r in guest.ok("GET", by_author)] == ["Публичный"]
    assert sorted(r["name"] for r in author.ok("GET", by_author)) == ["Личный", "Публичный"]
    assert guest.ok("GET", f"/recipes?author={quote('никто')}") == []
    assert guest.get(f"/brewers/{quote('никто')}")[0] == 404

    listed = guest.ok("GET", "/recipes")
    assert listed[0]["author"]["name"] == "Открытый" and listed[0]["author"]["id"] == brewer["id"]
    detail = guest.ok("GET", f"/recipes/{public}")
    for shown in (brewer, listed, detail):                                   # почты нет нигде
        assert "secret.person" not in json.dumps(shown, ensure_ascii=False)
