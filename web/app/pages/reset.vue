<script setup lang="ts">
// Ссылка из письма: задать новый пароль. После сохранения человек сразу вошёл.
const auth = useAuthStore()
const drawer = useAuthDrawer()
const route = useRoute()
const toast = useToast()
const token = computed(() => (typeof route.query.token === 'string' ? route.query.token : ''))
const form = reactive({ password: '' })
const { pending, error, run } = useAuthForm()

async function submit() {
  if (!await run(() => auth.reset(token.value, form.password))) return
  toast.add({ title: 'Пароль изменён', color: 'success', icon: 'i-lucide-circle-check' })
  await navigateTo('/')
}
</script>

<template>
  <UDashboardPanel id="reset">
    <template #header>
      <UDashboardNavbar title="Новый пароль">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="m-auto w-full max-w-sm py-6">
        <template v-if="!token">
          <UAlert
            color="warning"
            variant="subtle"
            icon="i-lucide-link-2-off"
            title="Ссылка неполная"
            description="Откройте её из письма целиком или запросите новую."
          />
          <UButton label="Запросить ссылку" size="lg" block class="mt-8" @click="drawer.show('forgot')" />
        </template>

        <template v-else>
          <h1 class="text-2xl font-semibold text-highlighted">Новый пароль</h1>
          <p class="mt-2 text-muted">После сохранения вы сразу войдёте, а входы на других устройствах закроются.</p>
          <UForm :state="form" :validate="s => checkNewPassword(s.password)" :validate-on="['change']" class="mt-8 space-y-5" @submit="submit">
            <UFormField label="Новый пароль" name="password" :help="`Не короче ${PASSWORD_MIN} символов`">
              <AuthPassword v-model="form.password" autocomplete="new-password" />
            </UFormField>
            <UAlert v-if="error" color="error" variant="subtle" icon="i-lucide-circle-alert" :title="error">
              <template #actions>
                <UButton label="Запросить новую ссылку" color="error" variant="link" size="sm" class="px-0" @click="drawer.show('forgot')" />
              </template>
            </UAlert>
            <UButton type="submit" label="Сохранить и войти" size="lg" block :loading="pending" />
          </UForm>
        </template>
      </div>
    </template>
  </UDashboardPanel>
</template>
