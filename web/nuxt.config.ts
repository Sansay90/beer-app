// иконки, имена которых собираются динамически (сканер их не видит), + служебные иконки Nuxt UI —
// всё в клиентском бандле, чтобы интерфейс работал без интернета
const ICONS = [
  'hop', 'wheat', 'flame', 'book-open', 'settings', 'beer', 'wifi', 'wifi-off', 'bell', 'bell-ring', 'bell-off',
  'thermometer', 'timer', 'play', 'pause', 'power', 'droplets', 'waves', 'sliders-horizontal', 'circle-check',
  'circle-dot', 'circle', 'triangle-alert', 'history', 'upload', 'save', 'trash-2', 'copy', 'arrow-up', 'arrow-down',
  'plus', 'x', 'clock', 'activity', 'gauge', 'info', 'zap', 'flag', 'cloud-upload', 'file-plus', 'refresh-cw',
  'package-open', 'hand', 'chart-line', 'scroll-text', 'server', 'plug', 'hourglass', 'ellipsis-vertical', 'pencil',
  'check', 'thermometer-sun', 'circle-pause', 'circle-play', 'square',
  'leaf', 'sparkles', 'flask-conical', 'wrench', 'list-plus', 'send',
  'bean', 'candy', 'beaker', 'droplet', 'microscope', 'thermometer-snowflake', 'notebook-pen', 'tag', 'search-x',
  'arrow-up-down', 'calculator', 'bookmark', 'bookmark-check',
  'circle-user', 'log-out', 'log-in', 'mail-check', 'mail-warning', 'link-2-off', 'globe', 'lock', 'lock-keyhole',
  'eye-off', 'shield', 'users', 'camera', 'bell',
  // Nuxt UI
  'arrow-left', 'arrow-right', 'arrow-up-right', 'check', 'chevron-down', 'chevron-left', 'chevron-right', 'chevron-up',
  'chevrons-left', 'chevrons-right', 'circle-alert', 'circle-x', 'copy-check', 'ellipsis', 'eye', 'eye-off',
  'grip-vertical', 'loader-circle', 'menu', 'minus', 'monitor', 'moon', 'panel-left-close', 'panel-left-open',
  'rotate-ccw', 'search', 'sun', 'lightbulb',
].map(n => `lucide:${n}`)

export default defineNuxtConfig({
  modules: ['@nuxt/eslint', '@nuxt/ui', '@pinia/nuxt', '@vueuse/nuxt', 'nuxt-open-fetch'],
  // публичное — каталог и рецепт — рендерится на сервере (превью ссылок, поиск); личное — SPA (routeRules)
  ssr: true,
  devtools: { enabled: false },
  app: {
    head: {
      title: 'Пивоварня',
      htmlAttrs: { lang: 'ru' },
      meta: [{ name: 'viewport', content: 'width=device-width, initial-scale=1, viewport-fit=cover' }],
      link: [{ rel: 'icon', type: 'image/png', href: '/icon-192.png' }],
    },
  },
  css: ['~/assets/css/main.css', 'uplot/dist/uPlot.min.css'],
  runtimeConfig: {
    // куда сервер Nuxt проксирует /api (server/routes/api/[...].ts) — NUXT_API_SERVER
    apiServer: 'http://127.0.0.1:8000',
    // перед Nuxt свой прокси (nginx), и его X-Forwarded-* можно передать сервису — NUXT_TRUST_PROXY=1
    trustProxy: false,
    // адрес сервиса для браузера (NUXT_PUBLIC_API_BASE); пусто — /api того же сайта, что отдал страницу
    public: { apiBase: '' },
  },
  routeRules: {
    '/': { ssr: false },
    '/settings': { ssr: false },
    '/settings/**': { ssr: false },
    '/admin/**': { ssr: false },
    '/recipes/new': { ssr: false },
    '/recipes/*/edit': { ssr: false },
    '/verify': { ssr: false },
    '/reset': { ssr: false },
  },
  compatibilityDate: '2025-07-15',
  // модульные тесты утилит (vitest.config.ts) — тоже под nuxt typecheck
  typescript: {
    appTsConfig: { include: ['../test/unit/**/*'] },
  },
  // стиль кода — ESLint (eslint.config.mjs): без точек с запятой, одинарные кавычки, 2 пробела
  eslint: {
    config: {
      stylistic: { semi: false, quotes: 'single', indent: 2, commaDangle: 'always-multiline', braceStyle: '1tbs' },
    },
  },
  // шрифты из CSS (assets/css/main.css) @nuxt/fonts скачивает при сборке и раздаёт сам — с кириллицей и нужными весами
  fonts: {
    defaults: { weights: [400, 500, 600, 700], subsets: ['cyrillic-ext', 'cyrillic', 'latin-ext', 'latin'] },
    families: [{ name: 'Fira Sans' }, { name: 'Fira Sans Extra Condensed' }, { name: 'Literata' }],
  },
  icon: {
    clientBundle: { scan: true, icons: ICONS, sizeLimitKb: 512 },
  },
  // типизированный клиент сервиса: $api и useApi по OpenAPI-схеме (openapi.json, npm run api:types);
  // сам клиент — plugins/api.ts: адрес сервиса, cookie входа, истёкшая сессия
  openFetch: {
    clients: { api: { schema: 'openapi.json' } },
    disableNuxtPlugin: true,
    disableNitroPlugin: true,
  },
})
