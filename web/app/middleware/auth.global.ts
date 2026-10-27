// Кто вошёл — до первой страницы (права решает сервис). Меню показывает все разделы; закрытый раздел без входа
// зовёт войти сам (layouts/default.vue, meta.auth), вход — в выдвижной панели (components/auth/Drawer.vue).
let opening = true

export default defineNuxtRouteMiddleware(async (to) => {
  const first = opening
  opening = false
  const auth = useAuthStore()
  if (!auth.checked) await auth.refresh()
  // гость открыл приложение — начинает с каталога рецептов; «Варку» из меню он увидит как закрытый раздел
  if (first && !auth.user && to.path === '/') return navigateTo('/recipes')
})
