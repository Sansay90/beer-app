"""Роли: гость, пользователь, администратор (access.py) — что видно и что можно."""
import pytest


@pytest.fixture
def people(service):
    """owner — администратор с подтверждённой почтой; second — пользователь без подтверждения; guest — гость."""
    owner, second, guest = service.client(), service.client(), service.client()
    owner.signup("owner@test.local")
    owner.ok("POST", "/auth/verify", {"token": service.outbox.link("verify")})
    second.signup("second@test.local")
    return owner, second, guest


def test_roles_assigned(people):
    owner, second, _ = people
    assert owner.get("/auth/me")[1]["role"] == "admin"
    assert second.get("/auth/me")[1]["role"] == "user"


def test_guest(people, recipe):
    owner, _, guest = people
    rid = owner.ok("POST", "/recipes", recipe)["id"]
    assert guest.get("/recipes")[1] == []                           # личного не видно
    assert guest.get(f"/recipes/{rid}")[0] == 404
    assert guest.post("/recipes", recipe)[0] == 401
    assert guest.get("/recipes?mine=true")[0] == 401
    assert guest.get("/state")[0] == 401

    owner.ok("PUT", f"/recipes/{rid}/visibility", {"visibility": "public"})
    listed = guest.get("/recipes")[1]
    assert [r["name"] for r in listed] == [recipe["name"]]
    assert listed[0]["author"]["name"] == "owner" and listed[0]["mine"] is False and listed[0]["visibility"] == "public"
    meta = guest.get(f"/recipes/{rid}")[1]["meta"]
    assert meta["canEdit"] is False and meta["canModerate"] is False
    assert owner.get(f"/recipes/{rid}")[1]["meta"]["canEdit"] is True


def test_someone_elses_published_recipe(people, recipe):
    owner, second, _ = people
    rid = owner.ok("POST", "/recipes", recipe)["id"]
    owner.ok("PUT", f"/recipes/{rid}/visibility", {"visibility": "public"})
    assert second.put(f"/recipes/{rid}", {**recipe, "name": "Взлом"})[0] == 403
    assert second.delete(f"/recipes/{rid}")[0] == 403
    assert second.put(f"/recipes/{rid}/visibility", {"visibility": "private"})[0] == 403
    assert second.get(f"/recipes/{rid}")[0] == 200                 # смотреть и варить по нему можно


def test_publishing_needs_verified_email(service, people, recipe):
    owner, second, guest = people
    rid = second.ok("POST", "/recipes", {**recipe, "name": "Второй"})["id"]
    assert second.put(f"/recipes/{rid}/visibility", {"visibility": "public"})[0] == 403
    assert owner.get(f"/recipes/{rid}")[0] == 404                   # чужое личное не видит и администратор
    assert [r["name"] for r in second.get("/recipes?mine=true")[1]] == ["Второй"]
    second.ok("POST", "/auth/verify/resend")
    second.ok("POST", "/auth/verify", {"token": service.outbox.link("verify")})
    second.ok("PUT", f"/recipes/{rid}/visibility", {"visibility": "public"})
    assert guest.get(f"/recipes/{rid}")[0] == 200


def test_moderation(service, people, recipe):
    owner, second, guest = people
    second.ok("POST", "/auth/verify", {"token": service.outbox.link("verify")})
    rid = second.ok("POST", "/recipes", recipe)["id"]
    second.ok("PUT", f"/recipes/{rid}/visibility", {"visibility": "public"})

    meta = owner.get(f"/recipes/{rid}")[1]["meta"]
    assert meta["canModerate"] is True and meta["canEdit"] is False
    assert owner.put(f"/recipes/{rid}", recipe)[0] == 403           # править чужое нельзя и администратору
    owner.ok("PUT", f"/recipes/{rid}/visibility", {"visibility": "private"})
    assert guest.get(f"/recipes/{rid}")[0] == 404
    assert owner.put(f"/recipes/{rid}/visibility", {"visibility": "public"})[0] in (403, 404)

    second.ok("PUT", f"/recipes/{rid}/visibility", {"visibility": "public"})
    owner.ok("DELETE", f"/recipes/{rid}")
    assert second.get(f"/recipes/{rid}")[0] == 404


def test_admin_users(people):
    owner, second, guest = people
    assert guest.get("/admin/users")[0] == 401
    assert second.get("/admin/users")[0] == 403
    users = owner.ok("GET", "/admin/users")
    assert [u["email"] for u in users] == ["owner@test.local", "second@test.local"]
    me = owner.get("/auth/me")[1]
    assert owner.put(f"/admin/users/{me['id']}/role", {"role": "user"})[0] == 409      # последний администратор
    sid = next(u["id"] for u in users if u["email"] == "second@test.local")
    assert owner.ok("PUT", f"/admin/users/{sid}/role", {"role": "admin"})["role"] == "admin"
    assert second.get("/admin/users")[0] == 200
    assert owner.put(f"/admin/users/{sid}/role", {"role": "god"})[0] == 422
    assert owner.put("/admin/users/not-an-id/role", {"role": "user"})[0] == 404
