# brewapp — рецепты и пивоварня Easy Brew

Сервис для домашних пивоваров: рецепты с расчётом показателей, воды и фото пива, общий каталог опубликованных рецептов, история варок и управление пивоварней Easy Brew Connect через интернет. С пивоварней говорит агент в домашней сети, без облака Tuya и без замены прошивки; Smart Life продолжает работать параллельно.

Сайт: https://151-243-208-72.sslip.io — гость смотрит опубликованные рецепты, после входа по почте — свои рецепты и своя пивоварня.

```
браузер ──HTTPS──▶ nginx ─┬─ страницы ──▶ web (Nuxt: публичные страницы рендерит сервер)
                          └─ /api ──────▶ service (FastAPI, Postgres) ◀──WSS── agent ──Tuya, домашняя сеть──▶ пивоварня
```

| | |
|---|---|
| [service/](./service/README.md) | сервис: API, вход и роли, рецепты, варки, уведомления, связь с агентами |
| [agent/](./agent/README.md) | агент у пивоварни: подключение по домашней сети, протокол с сервисом; [протокол пивоварни](./agent/PROTOCOL.md) |
| [web/](./web/README.md) | интерфейс: Nuxt 4 + Nuxt UI |
| [shared/](./shared/README.md) | общие примеры расчётов для сервиса и интерфейса |
| [deploy/](./deploy/README.md) | сервер и выкатка |

Документация — [docs/](./docs/README.md):

- [features.md](./docs/features.md) — что умеет и по каким правилам; [scenarios.md](./docs/scenarios.md) — сценарии по шагам;
- [access.md](./docs/access.md) — доступы и роли; [api.md](./docs/api.md) — соглашения API; [data.md](./docs/data.md) — данные и формат рецепта;
- [architecture.md](./docs/architecture.md) — как устроено; [decisions.md](./docs/decisions.md) — почему так;
- [development.md](./docs/development.md) — запуск, тесты, как вносить изменения; [operations.md](./docs/operations.md) — сервер;
- [roadmap.md](./docs/roadmap.md) — куда идём; [glossary.md](./docs/glossary.md) — словарь;
- [CLAUDE.md](./CLAUDE.md) — правила для агентов разработки.

Быстрый старт для разработки — `service`: `docker compose up -d db`, `pip install -r requirements-dev.txt`, `python -m app`; `web`: `npm install`, `npm run dev` → http://localhost:3000. Подробно — [docs/development.md](./docs/development.md).
