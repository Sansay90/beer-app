# server — посредник brewapp

Бэкенд приложения. Держит **единственное** подключение к пивоварне Easy Brew Connect по домашней сети (модуль Tuya, протокол 3.4, библиотека [tinytuya](https://github.com/jasonacox/tinytuya)) и отдаёт интерфейсу:

- состояние и события — потоком **SSE** `GET /api/stream` (`event: state` — снимок, `event: event` — событие варки);
- команды — обычными `POST` (`/api/power`, `/api/manual`, `/api/recipe/start`, …);
- библиотеку рецептов — `GET/PUT/DELETE /api/recipes/{id}`, загрузка в пивоварню — `POST /api/recipes/{id}/upload`;
- фото пива — `GET/POST /api/recipes/{id}/photos`, картинка — `GET /api/photos/{id}` (`?thumb=true` — превью 480 px), `DELETE /api/photos/{id}`;
- историю варок — `GET /api/brews`, `GET /api/brews/{id}` (рецепт, температура, события).

Данные — в **Postgres**: пользователи, пивоварни, рецепты, варки, события, температура (см. «Данные» ниже).

Схема API — http://127.0.0.1:8000/docs (OpenAPI). Из неё генерируются TS-типы фронтенда: `cd ../web && npm run api:types`.

Протокол пивоварни (DP, формат рецепта, поведение на нагреве) — [PROTOCOL.md](./PROTOCOL.md).

## Запуск

### Локально

```powershell
cd brewapp\server
copy .env.example .env                           # пароль Postgres, адрес пивоварни
docker compose up -d db                          # база — в Docker (порт 5433 на этом ПК)
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m bridge.server           # http://127.0.0.1:8000
.venv\Scripts\python -m bridge.server --lan     # + доступ с телефона: http://<IP ПК>:8000
```

Адрес базы посредник берёт из `DATABASE_URL` (окружение или `.env`). Адрес пивоварни находится сам — по UDP-широковещанию модуля Tuya — и запоминается.

### В Docker

```powershell
cd brewapp\server
copy .env.example .env        # POSTGRES_PASSWORD, BREWERY_IP
docker compose up -d --build  # db (Postgres 17) + bridge
docker compose logs -f bridge
```

- **Адрес пивоварни задаётся явно** (`BREWERY_IP`, `BREWERY_VERSION` в `.env`): широковещание из сети Docker до модуля не доходит. Закрепите IP за пивоварней в роутере (DHCP-резервация).
- База живёт в томе `pgdata` — переживает пересборку и `docker compose down` (удаляет только `down -v`).
- Ключи (`devices.json`) — том, в образ не входят.
- Порт по умолчанию открыт только на этом ПК (`127.0.0.1:8000`). Для телефона поменять на `8000:8000` в `compose.yaml` — но авторизации нет, управлять сможет любой в Wi-Fi.

Переменные окружения: `DATABASE_URL` — база; `BREWERY_IP`, `BREWERY_VERSION` — пивоварня (перекрывают базу); `VAPID_PRIVATE_KEY`, `VAPID_SUBJECT` — уведомления (ниже); `BRIDGE_HOST`, `BRIDGE_PORT` — где слушать; `BREWAPP_DEVICES`, `BREWAPP_WEB_DIR` — пути.

## Уведомления (Web Push)

Подсказки пивоварни, закладки, конец программы, а во время варки — ошибка, выключение и потеря связи приходят системными уведомлениями, даже когда вкладка закрыта. Включаются в интерфейсе: «Настройки → Уведомления», отдельно на каждом устройстве. В уведомлении о закладке или подсказке есть кнопка «Заложил» / «Подтвердить», она шлёт команду посреднику напрямую.

- **Ключ сервера** — `VAPID_PRIVATE_KEY` в `.env`. Новый: `.venv\Scripts\python -m bridge.push`. Без ключа уведомления выключены (`/api/push/*` отвечают 503). Если сменить ключ, браузеры подпишутся заново при следующем открытии приложения.
- **`VAPID_SUBJECT`** — контакт владельца сервера для push-сервисов (`mailto:` или `https://`).
- Подписки хранятся в таблице `push_subscriptions`. Посредник принимает адреса только push-сервисов браузеров (Google, Mozilla, Microsoft, Apple), а отозванные подписки (404/410) удаляет сам.
- Браузер разрешает уведомления только на `localhost` или по HTTPS. На iPhone нужны HTTPS и приложение, добавленное на экран «Домой».

## Данные

```
users ─┬─ devices ─┬─ readings      температура во времени
       │           ├─ events        события пивоварни
       │           └─ brews         варки: рецепт (снимок), начало, конец, исход
       ├─ recipes                   рецепт целиком — JSONB (программа пивоварни выводится из него)
       │    └─ recipe_photos        фото пива: снимок и превью, подпись автора чужого фото
       └─ push_subscriptions        браузеры, подписанные на уведомления
```

- **Варка** открывается при запуске программы рецепта и закрывается в конце программы (`finished`) или при выключении пивоварни (`stopped`). Посредник перезапустили посреди варки — продолжит её, если пивоварня всё ещё в программе.
- **Журнал** (температура раз в ≥2 с, события) пишется отдельным потоком: медленная или упавшая база не тормозит связь с пивоварней.
- **Пользователь** пока один — владелец, создаётся при первом запуске; вход и регистрация — следующий шаг, данные к пользователю уже привязаны.
- **Фото** хранятся в базе (bytea) и удаляются вместе с рецептом. Интерфейс заранее уменьшает снимок до 1600 px и пережимает в JPEG (EXIF с координатами съёмки пропадает); посредник принимает JPEG, PNG и WebP до 10 МБ — тип по сигнатуре файла, — проверяет, что картинка открывается, и делает превью 480 px (Pillow). До 12 фото на рецепт.
- **Первичное наполнение** при старте: пивоварня — из `devices.json` (ключ обновится, если пивоварню переподключили к Smart Life).
- **Схема** меняется только миграциями Alembic (`migrations/`), они применяются при старте. После правки `bridge/models.py`: `.venv\Scripts\alembic revision --autogenerate -m "что изменилось"`.

## Устройство

```
bridge/
  device.py          подключение к пивоварне: фоновый поток, сторож связи, переподключение, команды с проверкой эха
  brew.py            смысл поверх DP: состояние, таймер шага, расписание закладок, события, варки
  push.py            Web Push: подписки браузеров, уведомления о событиях варки (отдельным потоком)
  models.py          таблицы Postgres (SQLModel)
  db.py              подключение, миграции при старте, первичное наполнение
  store.py           рецепты пользователя и журнал пивоварни (запись — отдельным потоком)
  program.py         рецепт → программа пивоварни: паузы, кипячение, напоминания о закладках
  recipe.py          программа ↔ бинарный блок DP 128
  schemas.py         Pydantic-схемы API — источник OpenAPI и TS-типов фронтенда
  server.py          FastAPI: HTTP API, SSE; раздаёт собранный фронтенд (../web/.output/public), если он есть
  export_openapi.py  выгрузка схемы в ../web/openapi.json
tools/probe.py       разведка протокола: снимок и журнал изменений DP
migrations/          миграции Alembic
dpmap.json           полная карта DP с пояснениями (для probe.py)
```

Модуль Tuya обслуживает не больше трёх одновременных локальных подключений — посредник занимает одно, Smart Life работает параллельно.

Приложение не вносит поправок под конкретный экземпляр или привычки пивовара. Потолок мощности — по модели (`bridge/recipe.py`, `MODEL_MAX_WATTS`); для неизвестной модели — `devices.max_watts` в базе.

## Ключи пивоварни (один раз)

Для локального управления нужны `device_id` и `local_key`. Их выдаёт облако Tuya через бесплатный кабинет разработчика.

1. Зарегистрироваться на [platform.tuya.com](https://platform.tuya.com).
2. **Cloud → Development → Create Cloud Project**: Industry — Smart Home, Development Method — Smart Home, Data Center — регион аккаунта Smart Life («Я» → шестерёнка → «Учётная запись и безопасность» → «Регион»; для России обычно **Central Europe**, при неудаче добавить **Western Europe**).
3. **Devices → Link App Account → Add App Account** → отсканировать QR из Smart Life («Я» → сканер справа вверху).
4. На вкладке **Overview** — **Access ID** и **Access Secret**; в **Devices** — **Device ID** пивоварни.
5. Из `brewapp\server`: `.venv\Scripts\python -m tinytuya wizard` — ввести Access ID, Secret, Device ID, регион (`eu` / `eu-w`), на вопросы о DP mappings и опросе сети — **Y**.

Мастер создаст `devices.json` (ключи) и `tinytuya.json` (секрет облака) — никому не пересылать. Подписка IoT Core нужна только для мастера. Если пивоварню сбросить и подключить к Smart Life заново, `local_key` сменится — мастер запустить ещё раз.

## Разведка протокола

```powershell
.venv\Scripts\python tools\probe.py dump     # снимок всех DP с именами из dpmap.json
.venv\Scripts\python tools\probe.py watch    # журнал изменений DP в реальном времени → logs/watch_*.csv
```
