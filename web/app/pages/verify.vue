<script setup lang="ts">
// Ссылка из письма: подтвердить почту. Открывается и без входа.
import type { Me } from '~/types'

const auth = useAuthStore()
const drawer = useAuthDrawer()
const route = useRoute()
const toast = useToast()
const token = typeof route.query.token === 'string' ? route.query.token : ''
const verified = ref<Me | null>(null)
const { pending, error, run } = useAuthForm()
const resend = useAuthForm()

onMounted(() => {
  if (token) run(async () => { verified.value = await auth.verify(token) })
  else error.value = 'Ссылка неполная — откройте её из письма целиком'
})

async function sendAgain() {
  if (await resend.run(auth.resendVerify)) {
    toast.add({ title: 'Письмо отправлено', description: `Новая ссылка — на ${auth.user?.email}.`, color: 'success', icon: 'i-lucide-mail-check' })
  }
}
</script>

<template>
  <UDashboardPanel id="verify">
    <template #header>
      <UDashboardNavbar title="Подтверждение почты">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="m-auto w-full max-w-sm py-6">
        <div v-if="pending || (!verified && !error)" class="flex items-center gap-3 text-muted">
          <UIcon name="i-lucide-loader-circle" class="size-5 animate-spin" />
          Подтверждаем почту…
        </div>

        <template v-else-if="verified">
          <div class="grid size-12 place-items-center rounded-xl bg-success/15 text-success">
            <UIcon name="i-lucide-circle-check" class="size-6" />
          </div>
          <h1 class="mt-6 text-2xl font-semibold text-highlighted">Почта подтверждена</h1>
          <p class="mt-2 text-muted">{{ verified.email }}</p>
          <UButton v-if="auth.user" to="/recipes" label="К рецептам" size="lg" block class="mt-8" />
          <UButton v-else label="Войти" size="lg" block class="mt-8" @click="drawer.show('login', '/recipes')" />
        </template>

        <template v-else>
          <div class="grid size-12 place-items-center rounded-xl bg-error/15 text-error">
            <UIcon name="i-lucide-circle-x" class="size-6" />
          </div>
          <h1 class="mt-6 text-2xl font-semibold text-highlighted">Почту подтвердить не вышло</h1>
          <p class="mt-2 text-muted">{{ error }}</p>
          <UButton
            v-if="auth.user && !auth.user.emailVerified"
            label="Прислать письмо ещё раз"
            size="lg"
            block
            class="mt-8"
            :loading="resend.pending.value"
            @click="sendAgain"
          />
          <UButton v-else-if="auth.user" to="/" label="На главную" size="lg" block class="mt-8" />
          <UButton v-else label="Войти" size="lg" block class="mt-8" @click="drawer.show('login')" />
          <p v-if="resend.error.value" class="mt-3 text-sm text-error">{{ resend.error.value }}</p>
        </template>
      </div>
    </template>
  </UDashboardPanel>
</template>
