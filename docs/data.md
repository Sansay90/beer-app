# Данные

Что и где хранится. Таблицы — `service/app/models.py`, схема меняется только миграциями Alembic (`service/migrations/`). Формат рецепта — схема `Recipe` в `service/app/recipes/schemas.py` (она же в OpenAPI).

## Где что лежит

| Где | Что |
|---|---|
| Postgres сервиса | пользователи и сессии, рецепты и фото, агенты (хэши токенов), пивоварни (модель, ограничения, профиль оборудования), варки, температура, события, подписки на уведомления |
| Агент: `data/state.json` | последняя программа в пивоварне (её пивоварня сама не отдаёт), что загружено из приложения (названия шагов и закладок), модель, теплоёмкость бака, незакрытая варка |
| Агент: `devices.json` | ключи Tuya пивоварни — только у агента |
| Браузер | cookie сессии; `localStorage` — единицы плотности и звук; подписка Web Push |

## Таблицы

```
users ─┬─ sessions                  входы
       ├─ auth_tokens               ссылки из писем
       ├─ agents                    агенты у пивоварен
       ├─ devices ─┬─ readings      температура во времени
       │           ├─ events        события пивоварни
       │           └─ brews         варки
       ├─ recipes ── recipe_photos  рецепт — JSONB; фото пива
       └─ push_subscriptions        браузеры, подписанные на уведомления
```

| Таблица | Главное |
|---|---|
| `users` | `email` (строчными, уникальна; пусто — владелец данных до входа), `password_hash` (scrypt), `email_verified_at`, `role` (`user` / `admin`), `name` — пока часть почты до `@` |
| `sessions` | `token_hash` (SHA-256 токена из cookie), `expires_at` — 30 дней с последнего захода, `user_agent` |
| `auth_tokens` | `kind` (`verify` / `reset`), `token_hash`, `expires_at`, `used_at` — одноразовые |
| `agents` | `token_hash`, `name`, `last_seen_at` |
| `devices` | `tuya_id` (уникален — пивоварня принадлежит одному пользователю), `agent_id` — через какой агент на связи, `model`, `limits` (JSONB, сообщает агент), `equipment` (JSONB: эффективность, испарение) |
| `recipes` | `data` (JSONB — рецепт целиком), `name` (для сортировки), `visibility` (`private` / `public`), `published_at`, `updated_at` |
| `recipe_photos` | `data` (снимок), `thumb` (JPEG до 480 px), `content_type`, `credit` |
| `brews` | `status` (`running` → `finished` / `stopped`), `recipe_id` (свой рецепт или пусто), `recipe` (снимок программы, как она была в пивоварне), `started_at`, `ended_at`, `energy_wh` |
| `readings` | `at`, `temp`, `target`, `step`, `status`, `brew_id` — не чаще раза в 2 с |
| `events` | `at`, `kind`, `text`, `data` (JSONB: подсказка, шаг, закладка), `brew_id` |
| `push_subscriptions` | `endpoint` (уникален: браузер подписан одним пользователем), ключи шифрования, `last_seen_at` |

Удаление каскадное: удалили рецепт — ушли его фото, а варки по нему остаются со снимком программы и без ссылки на рецепт.

## Рецепт

Рецепт описывает пиво (по мотивам BeerJSON). Единицы: плотность — SG, цвет — EBC, объём — л, засыпь — кг, хмель — г, температура — °C, мощность — W, время — мин (брожение — дни).

| Поле | Что |
|---|---|
| `name`, `notes` | название; описание — первый абзац идёт на карточку каталога |
| `style` | `{code, name}` — стиль BJCP 2021 (`code` пусто — свой стиль) |
| `batch` | `volume` — л после кипячения (к нему считаются OG, IBU, цвет), `efficiency` — % |
| `targets` | `og`, `fg`, `ibu`, `ebc`, `abv` — считает сервис при сохранении, присланные не сохраняются |
| `fermentables[]` | `name`, `kind` (`grain` / `adjunct` / `sugar` / `extract`), `amount` кг, `ebc`, `use` (`mash` / `boil` / `fermentation`), `minutes` — для кипячения |
| `hops[]` | `name`, `alpha` %, `amount` г, `use` (`mash` / `first_wort` / `boil` / `whirlpool` / `dry_hop`), `minutes` — до конца кипячения или время вирпула, `day` — день сухого охмеления |
| `miscs[]` | `name`, `kind` (`spice` / `fining` / `adjunct` / `equipment`), `amount` + `unit` (`g` / `kg` / `ml` / `pcs` / `pkg`), `use` (`mash` / `boil` / `whirlpool` / `fermentation` / `packaging`), `minutes` |
| `yeasts[]` | `name`, `form` (`dry` / `liquid`), `amount` + `unit`, `attenuation` — % |
| `water` | `ratio` — гидромодуль л/кг, `source` — исходная вода (Ca, Mg, Na, Cl, SO₄, HCO₃, мг/л; нули — осмос), `additions[]` — соль (г) или кислота (мл): `agent`, `amount`, `target` (`mash` / `sparge`) |
| `mash[]` | паузы: `name`, `temp`, `minutes`, `watts` |
| `boil` | `minutes`, `watts`; пусто — без кипячения |
| `fermentation[]` | шаги: `name`, `temp`, `days` |

Из рецепта выводятся (не хранятся): программа пивоварни, закладки и таймеры, объёмы воды и профиль ионов, показатели на лету — [features.md](./features.md).

## Программа для агента

Сервис отдаёт агенту программу в общем виде; агент записывает её в пивоварню и помнит в `state.json`:

```json
{"recipeId": "…", "name": "German Pils",
 "steps": [{"name": "Белковая пауза", "temp": 52, "minutes": 15, "watts": 2000, "boil": false},
           {"name": "Кипячение", "temp": 100, "minutes": 90, "watts": 2500, "boil": true}],
 "timers": [60, 15],
 "slots": [{"minutes": 60, "label": "Magnum 20 г",
            "items": [{"minutes": 60, "kind": "hop", "name": "Magnum", "amount": 20, "unit": "g", "whirlpool": null}]},
           {"minutes": 0, "label": "Tettnanger 40 г (вирпул 15 мин)",
            "items": [{"minutes": 0, "kind": "hop", "name": "Tettnanger", "amount": 40, "unit": "g", "whirlpool": 15}]}]}
```

`timers` — минуты, на которых пищит пивоварня (только строго внутри кипячения); `slots` — что класть по каждому напоминанию, включая начало и конец кипячения.

## Жизненный цикл

- **Варка** открывается, когда пивоварня запускает программу рецепта, и закрывается в её конце (`finished`) или при выключении (`stopped`) — решает агент. Варки, о которых подключившийся агент не знает, сервис закрывает как прерванные.
- **Сессия** продлевается при заходе не чаще раза в час; истёкшие остаются в таблице до чистки (чистки пока нет).
- **Температура и события** копятся без срока; при росте базы — прореживание старых точек (в планах).
- **Бэкапа базы по расписанию пока нет** — [operations.md](./operations.md#бэкап-базы).
