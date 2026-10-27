<script setup lang="ts">
// Раздел только для вошедших или администраторов (meta.auth страницы) — вместо страницы витрина: чем раздел хорош
// и как в него попасть. Сама страница тогда не создаётся и сервис не спрашивает.
// Маршрут — прямо из роутера: useRoute() Nuxt обновляет, когда отрисует новую страницу, а её тут может и не быть.
const router = useRouter()
const auth = useAuthStore()
const meta = computed(() => router.currentRoute.value.meta)
const gated = computed(() => (meta.value.auth === 'admin' && !auth.isAdmin) || (meta.value.auth === 'user' && !auth.user))
</script>

<template>
  <UDashboardGroup unit="rem">
    <AppSidebar />
    <AppAuthGate
      v-if="gated"
      :title="meta.title"
      :admin="meta.auth === 'admin'"
      :teaser="meta.teaser"
    />
    <slot v-else />
  </UDashboardGroup>
</template>
