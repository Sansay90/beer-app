# Данные

Что и где хранится. Таблицы — `service/app/models.py`, схема меняется только миграциями Alembic (`service/migrations/`). Формат рецепта — схема `Recipe` в `service/app/recipes/schemas.py` (она же в OpenAPI).

## Где что лежит

| Где | Что |
|---|---|
| Postgres сервиса | пользователи и сессии, рецепты и фото, агенты (хэши токенов), пивоварни (модель, ограничения), оборудование пивоваров, варки, температура, события, подписки на уведомления |
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
       │           └─ brews         варки с пивоварни (и без неё — записанные вручную)
       ├─ brews ── brew_entries     журнал варки: замеры, вехи, заметки
       ├─ recipes ── recipe_photos  рецепт — JSONB; фото пива
       ├─ favorites ── recipes      избранное: рецепты, сохранённые без копии
       ├─ recipe_votes ── recipes   лайки и дизлайки рецептов
       ├─ comments ── recipes       обсуждение; comment_votes — голоса за комментарии
       ├─ notifications ── comments, brews   уведомления на сайте: комментарий, ответ, напоминание о брожении
       └─ push_subscriptions        браузеры, подписанные на уведомления
```

| Таблица | Главное |
|---|---|
| `users` | `email` (строчными, уникальна; пусто — владелец данных до входа), `password_hash` (scrypt), `email_verified_at`, `role` (`user` / `admin`), `name` — ник (необязателен, его видят все), `name_key` — ник для сравнения (строчными, «ё» как «е», уникален), `avatar` (JPEG 256×256), `avatar_version` — в адресе аватара, чтобы новый не брался из кеша, `push_comments` и `push_brews` — системные уведомления о комментариях и напоминания о брожении (по умолчанию да) |
| `sessions` | `token_hash` (SHA-256 токена из cookie), `expires_at` — 30 дней с последнего захода, `user_agent` |
| `auth_tokens` | `kind` (`verify` / `reset`), `token_hash`, `expires_at`, `used_at` — одноразовые |
| `agents` | `token_hash`, `name`, `last_seen_at` |
| `devices` | `tuya_id` (уникален — пивоварня принадлежит одному пользователю), `agent_id` — через какой агент на связи, `model`, `limits` (JSONB, сообщает агент) |
| `equipment` | `user_id`, `name`, `kind` (`manual` — без подключения, `easybrew`), `device_id` (пивоварня, которую завёл агент; удалили — пусто), `volume` (л после кипячения), `efficiency`, `evaporation`, `kettle` (объём котла до краёв, л), `main` (одно у пользователя) |
| `recipes` | `data` (JSONB — рецепт целиком), `name` (для сортировки), `visibility` (`private` / `public`), `published_at`, `updated_at` |
| `recipe_photos` | `data` (снимок), `thumb` (JPEG до 480 px), `content_type`, `credit` |
| `recipe_votes` | `user_id` + `recipe_id` (ключ), `value` (1 / −1) |
| `comments` | `recipe_id`, `user_id`, `parent_id` (ответ: один уровень), `text`, `edited_at`, `deleted_at` (удалённый с ответами — пустой) |
| `comment_votes` | `user_id` + `comment_id` (ключ), `value` (1 / −1) |
| `notifications` | `user_id` — кому, `kind` (`comment` / `reply` / `brew`), у комментария — `actor_id` (кто написал), `recipe_id`, `comment_id`; у напоминания — `brew_id` и `data` (заголовок, текст); `created_at`, `read_at`; уходит вместе с комментарием (и при мягком удалении), рецептом, варкой или автором |
| `favorites` | `user_id` + `recipe_id` (ключ), `created_at` — ссылка, а не копия; рецепт сняли с публикации — из избранного пропадает вместе с доступом, удалили — запись удаляется |
| `brews` | `source` (`device` — с пивоварни, `manual` — записана вручную), `device_id` (пусто у записанной вручную; убрали пивоварню — варки остаются), `status` (исход программы пивоварни: `running` → `finished` / `stopped`; у партии без пивоварни — идёт ли варочный день; «Сварить» задним числом — сразу `finished`), `day_ended_at` (варочный день позади: задача дрожжей, «закончить» или сам через 36 ч; пусто — день идёт; конец программы его не ставит), `recipe_id` (свой или опубликованный рецепт, иначе пусто — по нему «сколько раз варили»: от пивовара не больше одной варки в день), `equipment_id` (на чём варили), `recipe` (снимок программы, как она была в пивоварне), `snapshot` (JSONB: рецепт партии — рецепт, пересчитанный под объём и эффективность оборудования на момент варки, с его испарением `batch.evaporation`; у варок до снимков пусто), `plan` (JSONB: OG, FG, крепость, объём, эффективность рецепта партии, этапы брожения, сухое охмеление по дням), `reminded` (JSONB: о чём из плана брожения уже напомнили), `started_at`, `ended_at`, `energy_wh` |
| `brew_entries` | `brew_id`, `at` (когда было — можно задним числом), `kind` (замер, веха, `note`, `step` — переход к шагу варочного дня, `stage` — к этапу брожения), `value` (SG, pH, л или °C — по виду; у `step` и `stage` — номер), `text` |
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
