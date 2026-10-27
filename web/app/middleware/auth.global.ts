// Кто вошёл — до первой страницы (права решает сервис). Меню показывает все разделы; закрытый раздел без входа
// зовёт войти сам (layouts/default.vue, meta.auth), вход — в выдвижной панели (components/auth/Drawer.vue).
// На сервере (каталог и рецепт) — по cookie посетителя; в браузере профиль приходит с отрисованной страницей.
export default defineNuxtRouteMiddleware(async (to) => {
  // первая страница этого открытия приложения: состояние — своё у каждого посетителя, не общее на сервере
  const opened = useState('app-opened', () => false)
  const first = !opened.value
  opened.value = true
  const auth = useAuthStore()
  if (!auth.checked) await auth.refresh()
  // гость открыл приложение — начинает с каталога рецептов; «Варку» из меню он увидит как закрытый раздел
  if (first && !auth.user && to.path === '/') return navigateTo('/recipes')
})
