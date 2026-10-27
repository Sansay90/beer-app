// Страницы помечают, кому они открыты: auth — 'user' (после входа) или 'admin'; teaser — чем раздел зовёт гостя
// (components/app/AuthGate.vue); title — заголовок закрытого раздела.
declare module '#app' {
  interface PageMeta {
    auth?: 'user' | 'admin'
    teaser?: 'brew' | 'recipe' | 'settings'
    title?: string
  }
}

export {}
