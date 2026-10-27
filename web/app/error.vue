<script setup lang="ts">
// Страница ошибки: такой страницы нет (404 — и рецепта, которого нет или он закрыт) или сервис не ответил (5xx).
// Отдаётся с этим кодом и при рендере на сервере — поисковики не запомнят её как рецепт.
import type { NuxtError } from '#app'
import { ru } from '@nuxt/ui/locale'

const props = defineProps<{ error: NuxtError }>()

const status = computed(() => props.error.status ?? props.error.statusCode ?? 500)
const view = computed(() => {
  if (status.value === 404) {
    return { title: 'Такой страницы нет', text: 'Рецепт удалили или сняли с публикации — или в ссылке опечатка.' }
  }
  return {
    title: 'Не получилось открыть страницу',
    text: status.value >= 500 ? 'Сервис не отвечает — попробуйте чуть позже.' : props.error.message,
  }
})

useSeoMeta({ title: () => `${view.value.title} — Пивоварня`, robots: 'noindex' })
</script>

<template>
  <UApp :locale="ru">
    <UError
      :error="{ status, statusText: view.title, message: view.text }"
      redirect="/recipes"
      :clear="{ label: 'В каталог рецептов', icon: 'i-lucide-book-open' }"
      class="min-h-dvh"
    />
  </UApp>
</template>
