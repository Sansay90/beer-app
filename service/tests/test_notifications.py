"""Уведомления на сайте: автору рецепта — о комментарии, автору комментария — об ответе, о своём — никому;
прочитано, удаление комментария, снятие рецепта с публикации; push — по настройке."""
import pytest


@pytest.fixture
def people(service):
    """author — администратор с подтверждённой почтой (может публиковать); reader и other — пользователи."""
    author, reader, other = service.client(), service.client(), service.client()
    author.signup("author@test.local")
    author.ok("POST", "/auth/verify", {"token": service.outbox.link("verify")})
    reader.signup("reader@test.local")
    other.signup("other@test.local")
    return author, reader, other


@pytest.fixture
def published(people, recipe):
    author = people[0]
    rid = author.ok("POST", "/recipes", recipe)["id"]
    author.ok("PUT", f"/recipes/{rid}/visibility", {"visibility": "public"})
    return rid


@pytest.fixture
def pushes(service):
    """Push не уходит наружу, а копится здесь: (кому, уведомление)."""
    sent = []
    service.state.pusher.notify = lambda user_id, note: sent.append((str(user_id), note))
    return sent


def unread(client):
    return client.ok("GET", "/notifications/unread")["count"]


def test_who_gets_notified(people, published, recipe):
    author, reader, other = people
    rid = published
    question = reader.ok("POST", f"/recipes/{rid}/comments", {"text": "Какой зазор валков?"})
    assert unread(author) == 1 and unread(reader) == 0                       # о своём — не сообщаем

    [n] = author.ok("GET", "/notifications")
    assert n["kind"] == "comment" and not n["read"] and n["actor"]["name"] == "reader"
    assert n["recipe"] == {"id": rid, "name": recipe["name"]}
    assert n["commentId"] == question["id"] and n["text"] == "Какой зазор валков?"

    answer = author.ok("POST", f"/recipes/{rid}/comments", {"text": "0,8 мм", "parentId": question["id"]})
    assert unread(reader) == 1 and unread(author) == 1                       # свой ответ автору не приходит
    assert reader.ok("GET", "/notifications")[0]["kind"] == "reply"

    # ответ на ответ встаёт в ветку, но узнаёт о нём тот, кому ответили; автор рецепта — одно уведомление
    other.ok("POST", f"/recipes/{rid}/comments", {"text": "А для пшеницы?", "parentId": answer["id"]})
    kinds = [x["kind"] for x in author.ok("GET", "/notifications")]
    assert kinds == ["reply", "comment"] and unread(reader) == 1


def test_read(people, published):
    author, reader, other = people
    rid = published
    first = reader.ok("POST", f"/recipes/{rid}/comments", {"text": "Сварил"})
    reader.ok("POST", f"/recipes/{rid}/comments", {"text": "Вышло отлично"})
    newest, oldest = author.ok("GET", "/notifications")
    assert oldest["commentId"] == first["id"]                                # новые первыми

    other.ok("POST", "/notifications/read", {"ids": [newest["id"]]})          # чужое отметить нельзя — молча
    author.ok("POST", "/notifications/read", {"ids": [newest["id"], "мусор"]})
    assert unread(author) == 1
    assert [x["read"] for x in author.ok("GET", "/notifications")] == [True, False]
    author.ok("POST", "/notifications/read", {})
    assert unread(author) == 0


def test_deleted_comment_takes_its_notices(people, published):
    author, reader, _ = people
    rid = published
    question = reader.ok("POST", f"/recipes/{rid}/comments", {"text": "Вопрос"})
    answer = author.ok("POST", f"/recipes/{rid}/comments", {"text": "Ответ", "parentId": question["id"]})
    reader.ok("DELETE", f"/comments/{question['id']}")                       # с ответом — остаётся пустым
    assert author.ok("GET", "/notifications") == []
    author.ok("DELETE", f"/comments/{answer['id']}")                         # без ответов — совсем
    assert reader.ok("GET", "/notifications") == []


def test_unpublished_recipe_hides_notices(people, published):
    author, reader, _ = people
    rid = published
    question = reader.ok("POST", f"/recipes/{rid}/comments", {"text": "Вопрос"})
    author.ok("POST", f"/recipes/{rid}/comments", {"text": "Ответ", "parentId": question["id"]})
    author.ok("PUT", f"/recipes/{rid}/visibility", {"visibility": "private"})
    assert reader.ok("GET", "/notifications") == [] and unread(reader) == 0  # рецепт больше не виден
    assert len(author.ok("GET", "/notifications")) == 1                      # свой — виден


def test_push_follows_setting(service, people, published, recipe, pushes):
    author, reader, _ = people
    rid = published
    assert service.client().get("/notifications")[0] == 401
    assert author.ok("GET", "/notifications/settings") == {"pushComments": True}

    c = reader.ok("POST", f"/recipes/{rid}/comments", {"text": "Какой зазор валков?"})
    [(to, note)] = pushes
    assert to == author.ok("GET", "/auth/me")["id"]
    assert note["title"] == f"Новый комментарий к рецепту «{recipe['name']}»"
    assert note["body"] == "reader: Какой зазор валков?" and note["url"] == f"/recipes/{rid}#c-{c['id']}"

    assert author.ok("PUT", "/notifications/settings", {"pushComments": False}) == {"pushComments": False}
    reader.ok("POST", f"/recipes/{rid}/comments", {"text": "Ещё вопрос"})
    assert len(pushes) == 1 and unread(author) == 2                          # на сайте — всё равно
