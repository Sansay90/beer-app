"""Обсуждение рецепта: комментарии, ответы в одну ветку, правка и удаление, голоса за рецепт и комментарии,
счётчики в списке и на странице рецепта."""
import pytest


@pytest.fixture
def people(service):
    """author — первый, поэтому администратор (у себя на ПК), с подтверждённой почтой; reader — пользователь."""
    author, reader, guest = service.client(), service.client(), service.client()
    author.signup("author@test.local")
    author.ok("POST", "/auth/verify", {"token": service.outbox.link("verify")})
    reader.signup("reader@test.local")
    return author, reader, guest


@pytest.fixture
def published(people, recipe):
    author = people[0]
    rid = author.ok("POST", "/recipes", recipe)["id"]
    author.ok("PUT", f"/recipes/{rid}/visibility", {"visibility": "public"})
    return rid


def test_comments_and_replies(people, published):
    author, reader, guest = people
    rid = published
    assert guest.post(f"/recipes/{rid}/comments", {"text": "Привет"})[0] == 401
    assert reader.post(f"/recipes/{rid}/comments", {"text": "   "})[0] == 400

    first = reader.ok("POST", f"/recipes/{rid}/comments", {"text": "Какой зазор валков?"})
    assert first["author"]["name"] == "reader" and first["canEdit"] and first["parentId"] is None
    answer = author.ok("POST", f"/recipes/{rid}/comments", {"text": "0,8 мм", "parentId": first["id"]})
    deeper = reader.ok("POST", f"/recipes/{rid}/comments", {"text": "Спасибо!", "parentId": answer["id"]})
    assert answer["parentId"] == first["id"] and deeper["parentId"] == first["id"]   # ответ на ответ — в ветку

    listed = guest.ok("GET", f"/recipes/{rid}/comments")                     # читать может и гость
    assert [c["text"] for c in listed] == ["Какой зазор валков?", "0,8 мм", "Спасибо!"]
    assert not any(c["canEdit"] or c["canDelete"] for c in listed)
    assert guest.ok("GET", "/recipes")[0]["comments"] == 3
    assert guest.ok("GET", f"/recipes/{rid}")["meta"]["comments"] == 3


def test_edit_and_delete(people, published):
    author, reader, _ = people
    rid = published
    mine = reader.ok("POST", f"/recipes/{rid}/comments", {"text": "Сварил"})
    theirs = author.ok("POST", f"/recipes/{rid}/comments", {"text": "Как вышло?", "parentId": mine["id"]})

    assert reader.request("PATCH", f"/comments/{theirs['id']}", {"text": "Взлом"})[0] == 403
    edited = reader.ok("PATCH", f"/comments/{mine['id']}", {"text": "Сварил дважды"})
    assert edited["text"] == "Сварил дважды" and edited["edited"] is True
    assert reader.delete(f"/comments/{theirs['id']}")[0] == 403              # чужое — только администратору

    reader.ok("DELETE", f"/comments/{mine['id']}")                           # с ответом — остаётся пустым
    shown = reader.ok("GET", f"/recipes/{rid}/comments")
    assert shown[0]["deleted"] is True and shown[0]["text"] == "" and shown[0]["author"] is None
    assert reader.ok("GET", "/recipes")[0]["comments"] == 1                  # удалённые не считаются

    author.ok("DELETE", f"/comments/{theirs['id']}")                         # последний ответ — уходит и пустой
    assert reader.ok("GET", f"/recipes/{rid}/comments") == []


def test_admin_removes_someone_elses_comment(people, published):
    author, reader, _ = people
    c = reader.ok("POST", f"/recipes/{published}/comments", {"text": "Спам"})
    assert author.ok("GET", f"/recipes/{published}/comments")[0]["canDelete"] is True
    author.ok("DELETE", f"/comments/{c['id']}")
    assert author.ok("GET", f"/recipes/{published}/comments") == []


def test_votes(people, published):
    author, reader, guest = people
    rid = published
    assert guest.put(f"/recipes/{rid}/vote", {"value": 1})[0] == 401
    assert author.put(f"/recipes/{rid}/vote", {"value": 1})[0] == 403         # за свой — нельзя
    assert reader.put(f"/recipes/{rid}/vote", {"value": 5})[0] == 400

    assert reader.ok("PUT", f"/recipes/{rid}/vote", {"value": 1}) == {"likes": 1, "dislikes": 0, "vote": 1}
    assert reader.ok("PUT", f"/recipes/{rid}/vote", {"value": -1}) == {"likes": 0, "dislikes": 1, "vote": -1}
    assert reader.ok("GET", f"/recipes/{rid}")["meta"]["vote"] == -1
    card = guest.ok("GET", "/recipes")[0]
    assert (card["likes"], card["dislikes"]) == (0, 1)
    assert reader.ok("PUT", f"/recipes/{rid}/vote", {"value": 0}) == {"likes": 0, "dislikes": 0, "vote": 0}

    c = author.ok("POST", f"/recipes/{rid}/comments", {"text": "Варите на здоровье"})
    assert author.put(f"/comments/{c['id']}/vote", {"value": 1})[0] == 403
    assert reader.ok("PUT", f"/comments/{c['id']}/vote", {"value": 1})["likes"] == 1
    shown = reader.ok("GET", f"/recipes/{rid}/comments")[0]
    assert (shown["likes"], shown["vote"]) == (1, 1)
    assert guest.ok("GET", f"/recipes/{rid}/comments")[0]["vote"] == 0


def test_private_recipe_discussion_hidden(people, recipe):
    author, reader, guest = people
    rid = author.ok("POST", "/recipes", recipe)["id"]                       # личный
    author.ok("POST", f"/recipes/{rid}/comments", {"text": "Заметка себе"})
    assert reader.get(f"/recipes/{rid}/comments")[0] == 404
    assert reader.post(f"/recipes/{rid}/comments", {"text": "Эй"})[0] == 404
    assert reader.put(f"/recipes/{rid}/vote", {"value": 1})[0] == 404
    assert guest.get(f"/recipes/{rid}/comments")[0] == 404


def test_deleted_recipe_takes_discussion(people, published):
    author, reader, _ = people
    c = reader.ok("POST", f"/recipes/{published}/comments", {"text": "Вкусно"})
    author.ok("DELETE", f"/recipes/{published}")
    assert reader.delete(f"/comments/{c['id']}")[0] == 404


def test_comment_rate_limit(people, published):
    _, reader, _ = people
    for i in range(5):
        reader.ok("POST", f"/recipes/{published}/comments", {"text": f"Комментарий {i}"})
    assert reader.post(f"/recipes/{published}/comments", {"text": "Шестой"})[0] == 429
