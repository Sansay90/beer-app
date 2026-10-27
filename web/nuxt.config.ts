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
  'arrow-up-down', 'calculator',
  // Nuxt UI
  'arrow-left', 'arrow-right', 'arrow-up-right', 'check', 'chevron-down', 'chevron-left', 'chevron-right', 'chevron-up',
  'chevrons-left', 'chevrons-right', 'circle-alert', 'circle-x', 'copy-check', 'ellipsis', 'eye', 'eye-off',
  'grip-vertical', 'loader-circle', 'menu', 'minus', 'monitor', 'moon', 'panel-left-close', 'panel-left-open',
  'rotate-ccw', 'search', 'sun', 'lightbulb',
].map(n => `lucide:${n}`)

export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  // статическая сборка: раздаётся посредником, позже упаковывается в Capacitor / PWA
  ssr: false,
  devtools: { enabled: false },
  modules: ['@nuxt/ui', '@pinia/nuxt', '@vueuse/nuxt'],
  css: ['~/assets/css/main.css', 'uplot/dist/uPlot.min.css'],
  icon: {
    clientBundle: { scan: true, icons: ICONS, sizeLimitKb: 512 },
  },
  app: {
    head: {
      title: 'Пивоварня',
      htmlAttrs: { lang: 'ru' },
      meta: [{ name: 'viewport', content: 'width=device-width, initial-scale=1, viewport-fit=cover' }],
      link: [{ rel: 'icon', type: 'image/png', href: '/icon-192.png' }],
    },
  },
  runtimeConfig: {
    // адрес посредника; пусто — тот же хост, что отдал страницу (в dev — 127.0.0.1:8000)
    public: { bridge: '' },
  },
})
