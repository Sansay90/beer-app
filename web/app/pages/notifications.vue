<script setup lang="ts">
// Уведомления: комментарии к моим рецептам, ответы мне и напоминания о брожении, новые первыми. Открыл список —
// всё прочитано: новые подсвечены до ухода со страницы, метка в меню гаснет сразу. Нажал — комментарий на странице
// рецепта или варка.
import type { Notice } from '~/types'

definePageMeta({ auth: 'user', title: 'Уведомления' })

const notices = useNotifications()
const { data: items, status, error } = useApi('/api/notifications', { key: 'notifications', default: () => [] })
useErrorToast(error)

watch(items, (list) => {
  if (list.some(n => !n.read)) notices.readAll().catch(() => {})
}, { immediate: true })

const title = (n: Notice) => (n.kind === 'brew'
  ? `${n.title} — «${n.brew?.name}»`
  : `${n.kind === 'reply' ? 'Вам ответили в рецепте' : 'Новый комментарий к рецепту'} «${n.recipe?.name}»`)
const link = (n: Notice) => (n.kind === 'brew' ? `/brews/${n.brew?.id}` : `/recipes/${n.recipe?.id}#c-${n.commentId}`)
</script>

<template>
  <UDashboardPanel id="notifications">
    <template #header>
      <UDashboardNavbar title="Уведомления">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="mx-auto w-full max-w-3xl">
        <UCard v-if="items.length" :ui="{ body: 'p-0 sm:p-0' }">
          <ul class="divide-y divide-default">
            <li v-for="n in items" :key="n.id">
              <NuxtLink
                :to="link(n)"
                class="flex gap-3 px-4 py-4 transition hover:bg-elevated/60 sm:px-6"
                :class="!n.read && 'bg-primary/5'"
              >
                <UserAvatar v-if="n.actor" :user="n.actor" class="size-10 shrink-0" />
                <div v-else class="grid size-10 shrink-0 place-items-center rounded-full bg-primary/15 text-primary">
                  <UIcon name="i-lucide-calendar" class="size-5" />
                </div>
                <div class="min-w-0 flex-1">
                  <div class="flex items-start gap-2">
                    <p class="min-w-0 flex-1 text-base text-highlighted" :class="!n.read && 'font-semibold'">
                      {{ title(n) }}
                    </p>
                    <span v-if="!n.read" class="mt-2 size-2.5 shrink-0 rounded-full bg-primary" aria-label="новое" />
                  </div>
                  <p class="mt-1 line-clamp-2 text-base text-muted">
                    <span v-if="n.actor" class="font-medium text-toned">{{ brewerName(n.actor) }}:</span> {{ n.text }}
                  </p>
                  <NuxtTime :datetime="n.createdAt * 1000" relative locale="ru-RU" class="mt-1 block text-sm text-dimmed" />
                </div>
              </NuxtLink>
            </li>
          </ul>
        </UCard>
        <UEmpty
          v-else-if="status === 'success'"
          icon="i-lucide-bell"
          title="Уведомлений пока нет"
          description="Здесь появятся комментарии к вашим рецептам, ответы на ваши комментарии и напоминания о брожении."
          variant="naked"
        />
      </div>
    </template>
  </UDashboardPanel>
</template>
