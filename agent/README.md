# agent — агент brewapp

Программа рядом с пивоварней. Держит **единственное** подключение к Easy Brew Connect по домашней сети (модуль Tuya, протокол 3.4, библиотека [tinytuya](https://github.com/jasonacox/tinytuya)) и связь с сервисом ([../service](../service/README.md)) по WebSocket. Соединение открывает сам агент, поэтому пивовару не нужны ни белый IP, ни проброс портов.

Агент понимает пивоварню: следит за шагами программы и таймером, напоминает о закладках, открывает и закрывает варки, оценивает расход электричества. Всё это уходит сервису сообщениями, хранит сервис. Сам агент помнит только то, что должно пережить перезапуск (`data/state.json`):

- последнюю программу в пивоварне — в `status` она не приходит;
- что загружено из приложения — названия шагов и закладок;
- модель пивоварни, теплоёмкость бака и незакрытую варку.

Ключи Tuya (`devices.json`) из агента никуда не уходят.

Протокол пивоварни (DP, формат рецепта, поведение на нагреве) — [PROTOCOL.md](./PROTOCOL.md).

## Запуск

```powershell
cd brewapp\agent
copy .env.example .env               # SERVICE_URL, AGENT_TOKEN, BREWERY_IP
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m agent
```

- **Токен** (`AGENT_TOKEN`) выдаёт сервис: в `brewapp\service` — `.venv\Scripts\python -m app.agents new`.
- **Ключи** — `devices.json` в этой папке (ниже — как получить).
- **Адрес пивоварни** без `BREWERY_IP` агент ищет сам — по UDP-широковещанию модуля Tuya — и запоминает. В Docker широковещание не доходит, там адрес обязателен. Лучше закрепить IP за пивоварней в роутере (DHCP-резервация).
- На одной машине с сервисом агента можно запустить и в Docker — он есть в `service/compose.yaml`.

Переменные окружения (или `.env`): `SERVICE_URL` — адрес сервиса для агентов (`ws://…/api/agent`); `AGENT_TOKEN`; `BREWERY_IP`, `BREWERY_VERSION` — пивоварня вместо автопоиска; `MAX_WATTS` — потолок мощности, если модели нет в списке (`agent/recipe.py`, `MODEL_MAX_WATTS`); `BREWAPP_DEVICES`, `BREWAPP_STATE` — пути к ключам и памяти.

Модуль Tuya обслуживает не больше трёх одновременных локальных подключений — агент занимает одно, Smart Life работает параллельно.

## Протокол

JSON по WebSocket `SERVICE_URL`, токен — в заголовке `Authorization: Bearer <токен>`. Неверный токен — сервис отвечает 403 ещё до соединения.

**Агент → сервис**

| `type` | когда | поля |
|---|---|---|
| `hello` | первым после подключения | `agent` — версия, `session` — id запуска агента, `device` {`tuyaId`, `name`}, `model`, `limits` (как `schemas.Limits`), `activeRecipeId` — рецепт из приложения в пивоварне, `brewId` — незакрытая варка, `brews` — варки, о которых у агента остались недосланные записи (их сервис не закрывает как прерванные) |
| `state` | при любом изменении | `data` — снимок для интерфейса (`schemas.Snapshot`) |
| `event` | событие пивоварни | `brewId`, `data` — `schemas.BrewEvent` |
| `reading` | температура, не чаще раза в 2 с | `brewId`, `at` (unix), `temp`, `target`, `step`, `status` |
| `brewStarted` | запущена программа | `id`, `at`, `name`, `recipeId`, `recipe` — программа пивоварни для истории |
| `brewUpdated` | раз в 30 с во время варки | `id`, `energyWh` |
| `brewFinished` | конец программы или выключение | `id`, `at`, `status` (`finished` / `stopped`), `energyWh` |
| `device` | узнали модель | `model`, `limits` |
| `result` | ответ на команду | `id`, `ok`, при ошибке `status` (400 / 404 / 502 / 504) и `error` |

У всех, кроме `hello`, `state` и `result`, есть `seq` — номер записи в пределах запуска агента. Агент держит запись у себя, пока сервис не подтвердит её номер, и после переподключения шлёт неподтверждённое снова. Так не теряется то, что ушло в незаметно оборвавшееся соединение. Состояние не нумеруется: после подключения агент сразу шлёт свежее.

**Сервис → агент**

| `type` | когда | поля |
|---|---|---|
| `welcome` | ответ на `hello` | `deviceId`; `program` — свежая программа загруженного рецепта или `forget` — его id, если рецепт удалён |
| `ack` | запись принята | `seq` |
| `command` | команда пивоварне | `id`, `name`, `args` |
| `program` | загруженный рецепт поправили | `program` |
| `forget` | загруженный рецепт удалили | `forget` — id рецепта |

**Команды** (`name` → `args`): `power` {`on`}, `manual` {`setpoint`, `minutes`, `watts`}, `run` {`run`}, `startRecipe`, `pump` {`on`}, `flow` {`level`}, `settings` {`calibration`, `boilCompensation`}, `confirmAlert`, `ackAddition` {`minutes`}, `upload` {`program`}. Команды не копятся: сервис шлёт их только на живое соединение.

**Программа** — рецепт в общем виде, как записать её в пивоварню, решает агент:

```json
{"recipeId": "…", "name": "German Pils",
 "steps": [{"name": "Белковая пауза", "temp": 52, "minutes": 15, "watts": 2000, "boil": false},
           {"name": "Кипячение", "temp": 100, "minutes": 90, "watts": 2500, "boil": true}],
 "timers": [60, 15],
 "slots": [{"minutes": 60, "items": [{"kind": "hop", "name": "Magnum", "amount": 20, "unit": "g", "minutes": 60}],
            "label": "Magnum 20 г"}]}
```

`timers` — минуты до конца кипячения, на которых пищит пивоварня (только строго внутри кипячения); `slots` — что класть по каждому напоминанию, включая закладки в начале и в конце кипячения, о которых напоминает само приложение.

## Устройство

```
agent/
  __main__.py        настройки, запуск
  link.py            связь с сервисом: переподключение, неподтверждённые записи, команды
  brew.py            смысл поверх DP: состояние, таймер шага, расписание закладок, события, варки
  device.py          подключение к пивоварне: фоновый поток, сторож связи, переподключение, команды с проверкой эха
  energy.py          оценка расхода электричества ТЭНом
  recipe.py          программа ↔ бинарный блок DP 128
  state.py           память между перезапусками (data/state.json)
tools/probe.py       разведка протокола: снимок и журнал изменений DP
dpmap.json           полная карта DP с пояснениями (для probe.py)
```

Агент не вносит поправок под конкретный экземпляр или привычки пивовара: в пивоварню уходит ровно та программа, что прислал сервис.

## Ключи пивоварни (один раз)

Для локального управления нужны `device_id` и `local_key`. Их выдаёт облако Tuya через бесплатный кабинет разработчика.

1. Зарегистрироваться на [platform.tuya.com](https://platform.tuya.com).
2. **Cloud → Development → Create Cloud Project**: Industry — Smart Home, Development Method — Smart Home, Data Center — регион аккаунта Smart Life («Я» → шестерёнка → «Учётная запись и безопасность» → «Регион»; для России обычно **Central Europe**, при неудаче добавить **Western Europe**).
3. **Devices → Link App Account → Add App Account** → отсканировать QR из Smart Life («Я» → сканер справа вверху).
4. На вкладке **Overview** — **Access ID** и **Access Secret**; в **Devices** — **Device ID** пивоварни.
5. Из `brewapp\agent`: `.venv\Scripts\python -m tinytuya wizard` — ввести Access ID, Secret, Device ID, регион (`eu` / `eu-w`), на вопросы о DP mappings и опросе сети — **Y**.

Мастер создаст `devices.json` (ключи) и `tinytuya.json` (секрет облака) — никому не пересылать. Подписка IoT Core нужна только для мастера. Если пивоварню сбросить и подключить к Smart Life заново, `local_key` сменится — мастер запустить ещё раз.

## Разведка протокола

```powershell
.venv\Scripts\python tools\probe.py dump     # снимок всех DP с именами из dpmap.json
.venv\Scripts\python tools\probe.py watch    # журнал изменений DP в реальном времени → logs/watch_*.csv
```
