<script setup lang="ts">
// Пользователи и их роли — только администратору (права — service/app/access.py).
import type { AdminUser, Role } from '~/types'

definePageMeta({ auth: 'admin', title: 'Пользователи' })

const { $api } = useNuxtApp()
const auth = useAuthStore()
const { exec } = useCommand()
const { data: users, status, error } = useApi('/api/admin/users', { key: 'admin-users', default: () => [] })
useErrorToast(error)

const ROLES = [
  { label: 'Пользователь', value: 'user' },
  { label: 'Администратор', value: 'admin' },
]

async function setRole(u: AdminUser, role: Role) {
  const saved = await exec(() => $api('/api/admin/users/{uid}/role', { method: 'PUT', path: { uid: u.id }, body: { role } }), 'Роль изменена')
  // не вышло (последний администратор) — список как был, выбор вернётся
  users.value = users.value.map(x => (x.id === u.id && saved ? saved : x))
  if (saved && u.id === auth.user?.id) await auth.refresh()
}

const date = (t: number) => new Date(t * 1000).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' })
</script>

<template>
  <UDashboardPanel id="admin-users">
    <template #header>
      <UDashboardNavbar title="Пользователи">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="mx-auto w-full max-w-4xl">
        <UCard v-if="users.length" :ui="{ body: 'p-0 sm:p-0' }">
          <ul class="divide-y divide-default">
            <li v-for="u in users" :key="u.id" class="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3 sm:px-6">
              <UIcon :name="u.role === 'admin' ? 'i-lucide-shield' : 'i-lucide-circle-user'" class="size-6 shrink-0 text-muted" />
              <div class="min-w-0 flex-1">
                <div class="truncate font-medium text-highlighted">
                  {{ u.email }}<span v-if="u.id === auth.user?.id" class="font-normal text-muted">{{ SEP }}вы</span>
                </div>
                <div class="num text-sm text-muted">
                  с {{ date(u.createdAt) }}{{ SEP }}{{ u.recipes }} {{ plural(u.recipes, 'рецепт', 'рецепта', 'рецептов') }}{{ SEP }}{{ u.emailVerified ? 'почта подтверждена' : 'почта не подтверждена' }}
                </div>
              </div>
              <USelect :model-value="u.role" :items="ROLES" class="w-44" aria-label="Роль" @update:model-value="v => setRole(u, v as Role)" />
            </li>
          </ul>
        </UCard>
        <UEmpty v-else-if="status === 'success'" icon="i-lucide-users" title="Пользователей пока нет" variant="naked" />
      </div>
    </template>
  </UDashboardPanel>
</template>
