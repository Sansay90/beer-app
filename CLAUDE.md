# CLAUDE.md

Инструкции для Claude Code (и других агентов — `AGENTS.md` ссылается сюда) в репозитории brewapp. Общение, документация, комментарии в коде и тексты интерфейса — **по-русски**; технические термины и имена из кода — как есть.

## Что это

Открытый русскоязычный сервис рецептов для домашних пивоваров СНГ с управлением пивоварней Easy Brew Connect. Сервис делается **для любых пивоваров и любых владельцев Easy Brew**: никаких поправок под конкретный экземпляр пивоварни или привычки одного пивовара — в пивоварню уходит ровно то, что задано в рецепте; параметры, зависящие от модели (мощность и т. п.), берутся от пивоварни, а не из констант.

- Документация — [docs/](docs/README.md): что умеет ([features](docs/features.md), [scenarios](docs/scenarios.md)), доступы ([access](docs/access.md)), устройство ([architecture](docs/architecture.md), [api](docs/api.md), [data](docs/data.md), [decisions](docs/decisions.md)), работа ([development](docs/development.md), [operations](docs/operations.md)), планы ([roadmap](docs/roadmap.md)).
- Документация меняется вместе с кодом, в том же изменении: поведение функции — `features.md` и `scenarios.md`, права — `access.md`, API и формат данных — `api.md` и `data.md`, решение «почему так» — `decisions.md`.
- `service/` — FastAPI + Postgres (пакет `app`, разделы `auth/`, `recipes/`, `brewery/`, `push/`, `notifications/`); `agent/` — агент у пивоварни (tinytuya, websockets); `web/` — Nuxt 4 + Nuxt UI (гибридный рендеринг: каталог и рецепт — на сервере, личное — в браузере); `shared/` — общие примеры расчётов; `deploy/` — сервер.

## Команды

```sh
ruff check service agent shared           # из корня; настройки — ruff.toml
cd service && pytest                       # нужен Postgres: docker compose up -d db (в service/)
cd agent && pytest
cd web && npm run lint && npm run test && npm run typecheck
cd web && npm run api:types                # после правки схем API: openapi.json → типы (nuxt-open-fetch)
cd service && alembic revision --autogenerate -m "…"   # после правки app/models.py
python -m app [serve|agents new|agents list|vapid|openapi]   # команды сервиса (из service/)
```

Python — из `.venv` своей папки (`service/.venv`, `agent/.venv`). На Windows в Git Bash heredoc ломает `\` и тройные кавычки — скрипты писать в файл.

MCP-серверы проекта (`.mcp.json`): **nuxt-ui** — компоненты, пропсы и примеры Nuxt UI; **context7** — актуальная документация библиотек (Nuxt, FastAPI, SQLModel, Pydantic, tinytuya…). Перед использованием API библиотеки сверяться с ними, а не с памятью.

Скилы проекта (`.claude/settings.json`, плагины ставятся при первом запуске Claude Code в `brewapp/`): **ui-ux-pro-max** (nextlevelbuilder) — стили, палитры, шрифтовые пары и UX-правила, в том числе для Nuxt UI; **example-skills** (anthropics/skills) — frontend-design, webapp-testing (проверка интерфейса через Playwright), theme-factory, canvas-design, skill-creator и др.; **academy-guide**. Для дизайна и вёрстки — сначала они. Скрипты ui-ux-pro-max, которые ходят в сеть (генерация логотипов и картинок через Gemini и др.), запускать только по просьбе пользователя.

## Правила кода

- **Сервис.** Новый эндпоинт — в `router.py` своего раздела. Кто спрашивает — `Viewer` / `CurrentUser` / `Admin`; общие объекты — зависимости из `deps.py` (`app.state`), глобального состояния нет. Отказ — ошибка из `errors.py` в модуле данных, роутер не ловит исключения ради HTTP-статуса. Права — только в `access.py`; интерфейс лишь прячет кнопки.
- **Схемы API** — источник типов интерфейса. Поменял `schemas.py` — `npm run api:types` (выгружает `web/openapi.json`, nuxt-open-fetch строит по нему типизированные `$api` / `useApi` и типы схем `#open-fetch-schemas/api`); типы в `web` руками не пишутся. CI сверяет `web/openapi.json` с сервисом.
- **База** — только миграциями Alembic; применённые миграции не править (ruff их не проверяет).
- **Два места одного правила:** программа пивоварни (`recipes/program.py` ≡ `web/app/utils/recipe.ts`), показатели (`recipes/calc.py` ≡ `web/app/utils/calc.ts`), пересчёт под оборудование (`recipes/scale.py` ≡ `web/app/utils/scale.ts`) и расписание брожения (`brewery/reminders.py` ≡ `fermentPlan` в `web/app/utils/brewlog.ts`). Меняется одно — меняется и второе, и примеры в `shared/` (`shared/README.md`). Показатели в базу пишет сервис.
- **Протокол агента** (`brewery/hub.py` ↔ `agent/link.py`, описание — `agent/README.md`): записи с `seq` подтверждаются `ack`; команды не копятся; ключи Tuya не покидают агента.
- **Интерфейс** — идиомы Nuxt: данные через `useApi` / `useAsyncData` и `$api` (nuxt-open-fetch), Pinia — только для клиентского состояния; страницы, которые рендерит сервер, не трогают `window` / `localStorage` при создании и не дают расхождений гидратации; без «самоделок» вроде глобальных ref вне сторов и строк-URL в компонентах. Тексты — для пивовара, без инструкций разработчику (про запуск, Docker и т. п.).
- **Стиль** — как в окружающем коде: короткие комментарии по-русски там, где они помогают; Python — ruff, строка до 120; TS/Vue — ESLint (без точек с запятой, одинарные кавычки).
- **Тесты** — к каждому изменению поведения. Сквозные тесты сервиса — с настоящим сервисом, базой и агентом на имитации пивоварни (`service/tests/support.py`, `agent/agent/fake.py`).

## Безопасность и железо

- `agent/devices.json`, `agent/tinytuya.json`, любые `.env` — ключи и пароли: не выводить, не коммитить, не пересылать.
- С настоящей пивоварней: DP 109 (модель) не записывать; нагрев и насос не включать без воды в котле.
- Команды пивоварне через интернет — по правилам [docs/roadmap.md, «Управление через интернет»](docs/roadmap.md#управление-через-интернет).

## Git и выкатка

Пуш в `main` сразу выкатывается на сервер (CI: линтеры, тесты, образ, SSH). Коммитить и пушить — только по просьбе. Перед пушем — проверки из «Команд».
