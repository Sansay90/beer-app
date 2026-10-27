<script setup lang="ts">
// Раздел только для вошедших или администраторов (meta.auth страницы) — вместо страницы витрина: чем раздел хорош
// и как в него попасть. Сама страница тогда не создаётся и сервис не спрашивает.
// Маршрут — прямо из роутера: useRoute() Nuxt обновляет, когда отрисует новую страницу, а её тут может и не быть.
// Вход истёк на открытой странице — она остаётся (несохранённые правки целы), войти снова — в панели поверх неё.
const router = useRouter()
const auth = useAuthStore()
const meta = computed(() => router.currentRoute.value.meta)
const lapsed = computed(() => auth.expiredOn === router.currentRoute.value.path)
const gated = computed(() => !lapsed.value
  && ((meta.value.auth === 'admin' && !auth.isAdmin) || (meta.value.auth === 'user' && !auth.user)))
// ширина и свёрнутость меню (UDashboardGroup persistent) запоминаются в cookie — только у вошедшего:
// гостю и поисковикам cookie не ставится
</script>

<template>
  <UDashboardGroup unit="rem" :persistent="!!auth.user">
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
