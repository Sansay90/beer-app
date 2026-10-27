# deploy — сервис в интернете

Каждый пуш в `main` выкатывается сам (`.github/workflows/deploy.yml`); pull request проходит только проверку:

1. **Проверка** — линтеры (ruff, ESLint), тесты сервиса с Postgres, агента и интерфейса, типы интерфейса, сверка схемы API с типами интерфейса.
2. **Образы** — сервис (`service/Dockerfile` → `ghcr.io/sansay90/beer-app`) и интерфейс, сервер Nuxt (`web/Dockerfile` → `ghcr.io/sansay90/beer-app-web`), каждый с тегами `latest` и `<коммит>`. Собираются в GitHub, не на сервере: сборке интерфейса нужно больше памяти, чем у сервера.
3. **Сервер** — по SSH под пользователем `deploy`: свежий `compose.yaml` в `/opt/brewapp`, `docker compose pull` нужных образов, `up -d`. Миграции базы сервис применяет сам при старте. После выкатки — проверка `/api/health` снаружи.

Повторить выкатку без пуша — Actions → «Проверка и выкатка» → Run workflow.

## Сервер

Сейчас: VPS `151.243.208.72`, Ubuntu 24.04, адрес сайта — https://151-243-208-72.sslip.io (sslip.io отдаёт IP по имени, сертификат — Let's Encrypt). На том же сервере работает VPN (AmneziaWG) — его не трогать.

```
/opt/brewapp/
  compose.yaml   из deploy/compose.yaml — кладёт выкатка
  .env           секреты сервера (образец — deploy/.env.example), только здесь
```

- **nginx** (на сервере, не в Docker) — HTTPS; `/api` — сервису на `127.0.0.1:8000`, остальное — интерфейсу на `127.0.0.1:3000`: `/etc/nginx/sites-available/brewapp` ← `deploy/nginx.conf`. Поменяли конфиг — скопировать на сервер и `nginx -t && systemctl reload nginx` (выкатка nginx не трогает).
- **Сертификат** продлевает certbot (таймер systemd, плагин nginx) по `server_name`.
- **База** — Postgres в контейнере, том `brewapp_pgdata`. Наружу не открыта.
- **Подкачка** 1 ГБ (`/swapfile`): памяти у сервера меньше гигабайта.
- **Пользователь `deploy`** — в группе docker, вход только по ключу; закрытая часть ключа — в секретах GitHub.

Секреты репозитория (Settings → Secrets → Actions): `DEPLOY_HOST`, `DEPLOY_SSH_KEY`, `DEPLOY_KNOWN_HOSTS` (`ssh-keyscan <адрес>`), `DEPLOY_URL`.

## Настройки сервера (`/opt/brewapp/.env`)

- `APP_URL` — адрес сайта: ссылки в письмах и проверка, что запросы пришли с него.
- `ADMIN_EMAILS` — почты администраторов. Регистрация с такой почтой сразу получает роль администратора и забирает данные, заведённые до входа; остальные — пользователи.
- `SMTP_*` — письма. Пока пусто, письма со ссылками только в журнале сервиса (`docker compose logs app`) — для открытой регистрации SMTP обязателен.
- `VAPID_*` — уведомления, `POSTGRES_PASSWORD` — база.

## Агент у пивоварни

Агент работает дома, рядом с пивоварней, и сам подключается к серверу: в `agent/.env` — `SERVICE_URL=wss://151-243-208-72.sslip.io/api/agent` и токен агента; запуск — `docker compose up -d --build` в `agent/` или из `.venv` ([agent/README.md](../agent/README.md#запуск)). Токен выдаётся на сервере:

```sh
cd /opt/brewapp && docker compose exec app python -m app agents new "Название" --email <почта владельца>
```

## Полезное

```sh
cd /opt/brewapp
docker compose ps                     # что запущено
docker compose logs -f app            # журнал сервиса
docker compose exec db psql -U brewapp brewapp
```
