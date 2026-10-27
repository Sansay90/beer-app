# web — интерфейс brewapp

Nuxt 4 + Nuxt UI 4, Pinia, nuxt-open-fetch; работает своим сервером Nuxt (Nitro, Node). **Гибридный рендеринг:** каталог `/recipes` и рецепт `/recipes/[id]` рендерятся на сервере — для поисковиков и превью ссылок (`useSeoMeta`), вошедшему — по его cookie; личное — варка, редактор, настройки, администрирование, `/verify`, `/reset` — приложение в браузере (`routeRules`, `ssr: false`). Что умеет интерфейс — [docs/features.md](../docs/features.md).

## Запуск

```sh
npm install                 # заодно nuxt prepare: типы API и ESLint
npm run dev                 # http://localhost:3000; /api Nuxt проксирует сервису (NUXT_API_SERVER, по умолчанию 127.0.0.1:8000)
```

Сервис для разработки — [docs/development.md](../docs/development.md#первый-запуск).

**/api — один адрес везде.** Браузер ходит на относительный `/api`. В разработке, при рендеринге на сервере (`$api` через `useRequestFetch` — с cookie посетителя) и в локальном Docker его принимает сам Nuxt — `server/routes/api/[...].ts` проксирует сервису потоком (SSE тоже), с `Set-Cookie` и `X-Forwarded-For/Proto` (`server/utils/forwarded.ts`: пришедшим X-Forwarded-* верит только с `NUXT_TRUST_PROXY=1`, иначе — адрес и схема самого соединения); в проде nginx шлёт `/api` сервису сам, мимо Nuxt. `Origin` проверяет сервис: свой сайт — его `APP_URL`, без него — этот ПК.

| Переменная | |
|---|---|
| `NUXT_API_SERVER` | куда сервер Nuxt проксирует `/api`; по умолчанию `http://127.0.0.1:8000`, в Docker — адрес сервиса в сети compose |
| `NUXT_TRUST_PROXY` | `1` — перед Nuxt свой прокси (nginx): его `X-Forwarded-For/Proto` передаются сервису; без флага пришедшие X-Forwarded-* отбрасываются — их мог написать посетитель |
| `NUXT_PUBLIC_API_BASE` | адрес сервиса для браузера, если он не на том же сайте (позже — Capacitor); пусто — `/api` того же сайта |
| `PORT`, `HOST` | где слушает сервер Nuxt (в образе — `3000`, `0.0.0.0`) |

| Скрипт | |
|---|---|
| `npm run dev` | dev-сервер с горячей перезагрузкой |
| `npm run build` | сборка сервера Nuxt в `.output` — сервис для неё не нужен |
| `npm run start` | запустить сборку: `node .output/server/index.mjs` (`npm run preview` — то же через Nuxt) |
| `npm run lint`, `lint:fix` | ESLint (`@nuxt/eslint`, стиль — в `nuxt.config.ts` и `eslint.config.mjs`) |
| `npm run test` | vitest: `test/unit` — чистые утилиты, без Nuxt |
| `npm run typecheck` | проверка типов, вместе с тестами |
| `npm run api:types` | выгрузить OpenAPI сервиса в `openapi.json` и пересобрать типы — после правки схем сервиса |

## Данные

- **Чтение** — средствами Nuxt: `useApi('/api/…')` (nuxt-open-fetch поверх `useFetch`) и `useAsyncData` с ключами. Состояние загрузки, ошибки и `refresh` — от них, без ручных флагов. Общие данные — по ключу: `recipes`, `recipe:<id>`, `limits`, `equipment`, `admin-users`.
- **Изменения** — `$api(...)` в обработчиках, потом `refreshNuxtData(ключ)` или `refresh()`.
- **Типы** — из `openapi.json`: пути, параметры, тела и ответы `$api` / `useApi` типизированы, схемы — `#open-fetch-schemas/api`, удобные имена — `app/types/index.ts`. Руками не пишутся.
- **Ошибки** — `utils/api.ts`: `errorText` достаёт текст для человека из ответа сервиса (`detail`) — и у ошибки, пришедшей с отрисованной на сервере страницей; `isOffline` — сервис недоступен (нет ответа или 502–504 от шлюза). 401 — вход истёк (`plugins/api.ts` → `auth.expired()`): открытая страница остаётся (несохранённое не теряется), панель входа — поверх неё. Нет рецепта или сервис не ответил — страница ошибки `error.vue` с честным кодом (404, 5xx), и при рендере на сервере.
- **Pinia** — только клиентское состояние: `auth` (кто вошёл), `brewery` (живое состояние пивоварни из SSE, история температуры, события, команды), `preferences` (единицы, звук).
- **Рендеринг на сервере** (каталог, рецепт): данные — `useApi` / `useAsyncData` (рецепт — с `await`: нет его — перенаправление в каталог), при создании компонентов — никаких `window`, `document`, `localStorage`. Настройки устройства (единицы, звук) — в cookie, их видит и сервер; пока их не меняли, cookie нет, гостю сервер cookie не ставит (ширина меню запоминается только у вошедшего); даты — `<NuxtTime>`, в часовом поясе посетителя; поток SSE открывается, когда страница ожила. Предупреждений гидратации быть не должно — проверять в dev-сборке.

## Устройство

```
app/
  app.vue, layouts/default.vue   UApp + боковая панель; закрытая страница без входа → витрина раздела
  error.vue                      страница ошибки: 404 и сбой сервиса, со ссылкой в каталог
  middleware/auth.global.ts      кто вошёл — до первой страницы (на сервере — по cookie); гостя с «/» — в каталог
  plugins/  api.ts               $api и useApi: адрес, cookie входа, 401 → выход
            brewery.client.ts    поток SSE /api/stream → стор пивоварни
            notifications.client.ts  звук на события и подсказки
            push.client.ts       сервис-воркер Web Push (public/sw.js)
  stores/   auth · brewery · preferences
  composables/  useRecipe · useLimits · useEquipment · usePhotoUrl — данные по ключам
                useCommand (действие с тостом ошибки) · useConfirm · useAuthDrawer · useAuthForm · usePush · useSound
  utils/    calc.ts      показатели рецепта и подгонка под рамки стиля (≡ service/app/recipes/calc.py)
            recipe.ts    рецепт ↔ форма, программа пивоварни и закладки (≡ service/app/recipes/program.py), проверка
            water.ts     вода: объёмы, соли, профиль ионов
            beer.ts      °P ↔ SG, ABV, цвет пива по EBC
            brew.ts      экран варки: фазы, таймеры, что делать дальше — чистые функции от снимка
            additions.ts закладки: типы, иконки, подписи · styles.ts — стили BJCP · format.ts · photo.ts · api.ts
            seo.ts       описание рецепта для превью ссылок и поисковиков
  data/     bjcp-2021.json — стили BJCP 2021 (scripts/bjcp.py, источник — beerjson/bjcp-json, MIT)
  components/  app/ — меню, витрины, подтверждение · auth/ — панель входа
               brew/ — карточки экрана варки · settings/ — карточки настроек
               recipe/ — карточка, бокал, фото, рамки стиля; editor/ — разделы редактора; view/ — разделы страницы рецепта
  pages/    index (варка) · recipes/ (каталог, new, [id], [id]/edit) · settings · admin/users · verify · reset
server/routes/api/[...].ts  /api → сервис (NUXT_API_SERVER): dev, рендеринг на сервере, локальный Docker
server/utils/forwarded.ts   заголовки запроса к сервису: X-Forwarded-* и доверие к своему прокси (NUXT_TRUST_PROXY)
test/unit/  vitest; shared.test.ts — сверка с общими примерами сервиса (../shared)
Dockerfile  образ сервера Nuxt: node:24-alpine, порт 3000, не root, HEALTHCHECK по «/» (SPA-оболочка — отвечает и без сервиса)
```

## Правила

- Расчёт показателей и программа пивоварни живут и здесь, и в сервисе — меняются вместе, с примерами в [shared/](../shared/README.md).
- Тексты — для пивовара: что сделать и что происходит, без инструкций разработчику и внутренностей протокола.
- Числа — по-русски: дробная часть через запятую (`format.ts`), плотность — в выбранных единицах (°P или SG).
- Цвет пива — шкала «в бокале» (`beer.ts`): тёмное пиво с ~50 EBC почти чёрное, а не красное.
