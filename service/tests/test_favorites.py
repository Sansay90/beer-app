"""Избранное: свой и чужой опубликованный рецепт сохраняются без копии; видно только тому, кто сохранил."""
import pytest


@pytest.fixture
def people(service):
    """author — с подтверждённой почтой (может публиковать), reader — пользователь, guest — гость."""
    author, reader, guest = service.client(), service.client(), service.client()
    author.signup("author@test.local")
    author.ok("POST", "/auth/verify", {"token": service.outbox.link("verify")})
    reader.signup("reader@test.local")
    return author, reader, guest


def favorites(client):
    return [r["name"] for r in client.get("/recipes?favorites=true")[1]]


def test_add_and_remove(people, recipe):
    author, reader, _ = people
    rid = author.ok("POST", "/recipes", recipe)["id"]
    author.ok("PUT", f"/recipes/{rid}/visibility", {"visibility": "public"})

    assert reader.get(f"/recipes/{rid}")[1]["meta"]["favorite"] is False
    reader.ok("PUT", f"/recipes/{rid}/favorite")
    reader.ok("PUT", f"/recipes/{rid}/favorite")                   # повторно — без ошибки и без дубля
    assert favorites(reader) == [recipe["name"]]
    assert reader.get(f"/recipes/{rid}")[1]["meta"]["favorite"] is True
    assert [r["favorite"] for r in reader.get("/recipes")[1]] == [True]

    assert favorites(author) == []                                  # избранное — у каждого своё
    assert author.get(f"/recipes/{rid}")[1]["meta"]["favorite"] is False

    reader.ok("DELETE", f"/recipes/{rid}/favorite")
    reader.ok("DELETE", f"/recipes/{rid}/favorite")
    assert favorites(reader) == []


def test_own_recipe(people, recipe):
    author, _, _ = people
    rid = author.ok("POST", "/recipes", recipe)["id"]
    author.ok("PUT", f"/recipes/{rid}/favorite")
    assert favorites(author) == [recipe["name"]]


def test_only_visible(people, recipe):
    author, reader, guest = people
    rid = author.ok("POST", "/recipes", recipe)["id"]
    assert reader.put(f"/recipes/{rid}/favorite")[0] == 404         # чужой личный рецепт не видно

    author.ok("PUT", f"/recipes/{rid}/visibility", {"visibility": "public"})
    reader.ok("PUT", f"/recipes/{rid}/favorite")
    author.ok("PUT", f"/recipes/{rid}/visibility", {"visibility": "private"})
    assert favorites(reader) == []                                  # сняли с публикации — пропал из избранного
    author.ok("PUT", f"/recipes/{rid}/visibility", {"visibility": "public"})
    assert favorites(reader) == [recipe["name"]]                    # опубликовали снова — вернулся

    assert guest.put(f"/recipes/{rid}/favorite")[0] == 401
    assert guest.get("/recipes?favorites=true")[0] == 401
    assert guest.get(f"/recipes/{rid}")[1]["meta"]["favorite"] is False


def test_deleted_recipe_leaves_favorites(people, recipe):
    author, reader, _ = people
    rid = author.ok("POST", "/recipes", recipe)["id"]
    author.ok("PUT", f"/recipes/{rid}/visibility", {"visibility": "public"})
    reader.ok("PUT", f"/recipes/{rid}/favorite")
    author.ok("DELETE", f"/recipes/{rid}")
    assert favorites(reader) == []
