# Эксплуатация

Как жить с сервисом на сервере: выкатка и откат, частые операции, «что делать, если…». Как сервер настроен — [deploy/README.md](../deploy/README.md).

Все команды — на сервере в `/opt/brewapp` под пользователем `deploy` (или root):

```sh
cd /opt/brewapp
docker compose ps                     # что запущено
docker compose logs -f app            # журнал сервиса (web — интерфейса, сервера Nuxt)
docker compose exec app python -m app <команда>   # команды сервиса: agents, vapid…
docker compose exec db psql -U brewapp brewapp    # база
```

На том же сервере работает VPN AmneziaWG (контейнер `amnezia-awg2`) — его не трогать.

## Выкатка

- **Обычная:** пуш в `main` → GitHub Actions: проверки → образ `ghcr.io/sansay90/beer-app:<коммит>` → сервер → проверка `/api/health`. Миграции сервис применяет сам при старте.
- **Повторить** без пуша — Actions → «Проверка и выкатка» → Run workflow.
- **Откатить:** надёжно — `git revert` плохого коммита и пуш. Быстро — прежний образ, если он ещё на сервере (`docker images ghcr.io/sansay90/beer-app`): `APP_TAG=<коммит> docker compose up -d app`. Схему базы откат образа **не** возвращает: если новая версия принесла миграцию, старый код может с ней не работать — тогда только revert или `docker compose exec app alembic downgrade -1` (осторожно: миграции, удаляющие данные, обратно их не вернут).

## Частые операции

### Токен агента

Пока нет привязки по коду с сайта, токен выдаёт оператор:

```sh
docker compose exec app python -m app agents new "Название" --email <почта владельца>
docker compose exec app python -m app agents list --email <почта владельца>
```

Токен печатается один раз — передать владельцу пивоварни для `AGENT_TOKEN` в `agent/.env`. Отозвать — удалить строку из `agents` (`delete from agents where name = …`); отзыв с сайта — в планах.

### Администратор

- Почты из `ADMIN_EMAILS` в `.env` получают роль администратора при **регистрации**.
- Уже зарегистрированному — роль даёт другой администратор («Пользователи»), а если администраторов нет: `update users set role = 'admin' where email = '…';`.

### Письма без SMTP

Пока `SMTP_HOST` пуст, письма не уходят, а их текст со ссылкой пишется в журнал:

```sh
docker compose logs app | grep -E "verify\?token|reset\?token"
```

Подключить SMTP — `SMTP_HOST`, `SMTP_PORT` (465 — SSL, иначе STARTTLS), `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` в `.env`, затем `docker compose up -d app`.

### Ключ уведомлений

`docker compose exec app python -m app vapid` → строку в `.env` (`VAPID_PRIVATE_KEY`) → `docker compose up -d app`. После смены ключа браузеры подпишутся заново при следующем открытии сайта.

### Бэкап базы

**По расписанию бэкапа пока нет** — это первое, что нужно сделать до открытия регистрации, и хранить копии не на этом же сервере. Вручную:

```sh
docker compose exec -T db pg_dump -U brewapp -Fc brewapp > brewapp-$(date +%F).dump      # копия
docker compose exec -T db pg_restore -U brewapp -d brewapp --clean < brewapp-2026-10-27.dump   # восстановить
```

### Сертификат и nginx

- Сертификат Let's Encrypt продлевает certbot сам (таймер systemd); проверка — `certbot renew --dry-run` (root).
- Конфиг nginx — `deploy/nginx.conf` → `/etc/nginx/sites-available/brewapp`, затем `nginx -t && systemctl reload nginx`. Выкатка nginx не трогает.

## Что делать, если…

**Сайт не открывается.** `docker compose ps`: `app` (сервис) или `web` (интерфейс) не `healthy` → `docker compose logs app` / `logs web` — чаще всего упала миграция или нет переменной в `.env`. nginx отвечает 502 на страницы — не слушает `web` (`127.0.0.1:3000`), на `/api` — `app` (`127.0.0.1:8000`). Страницы открываются, а рецептов нет — `web` не достучался до сервиса (`NUXT_API_SERVER` в `compose.yaml`).

**CI красный.** Job «Сервис и агент» — линтер ruff, тесты или устаревший `web/openapi.json` (в `web`: `npm run api:types`). Job «Интерфейс» — ESLint, vitest или типы. Пока проверка красная, образ не собирается и на сервер ничего не уходит.

**Агент не подключается.** Журнал агента (`docker compose logs -f` в `agent/` или окно `python -m agent`):
- «сервис не принял агента — проверьте AGENT_TOKEN» — токен неверный или отозван;
- «нет связи с сервисом» — адрес `SERVICE_URL` (`wss://<сайт>/api/agent`), интернет, сервис;
- агент подключился и сразу отключился — пивоварня уже привязана к другому пользователю (в журнале сервиса — «агент … не представился»).

**Пивоварня «не в сети», а агент на связи.** Агент не достучался до пивоварни: адрес `BREWERY_IP` (закрепить в роутере), пивоварня в той же сети, не больше трёх локальных подключений к модулю Tuya (агент, Smart Life, …). Ключ сменился после повторной привязки в Smart Life — заново получить `devices.json` ([agent/README.md](../agent/README.md#ключи-пивоварни-один-раз)).

**Письмо со ссылкой не пришло.** Без SMTP — ссылка в журнале (выше). С SMTP — в журнале «письмо на … не отправлено» с причиной. Лимит — 5 писем на почту в час.

**«Слишком много попыток».** Лимиты в памяти сервиса: пройдут сами через 15 минут (вход) или час (письма); перезапуск сервиса их сбрасывает.

## У себя на ПК

```sh
cd service && docker compose up -d db          # база для разработки и тестов
cd service && docker compose up -d --build     # + сервис и интерфейс, как на сервере: http://127.0.0.1:3000
cd agent && docker compose up -d --build       # агент — к адресу из agent/.env
```

Агент у пивоварни можно запускать и на ПК, и на Raspberry Pi или NAS — ему нужны только домашняя сеть и интернет.
