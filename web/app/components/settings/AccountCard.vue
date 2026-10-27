<script setup lang="ts">
const auth = useAuthStore()
const toast = useToast()
const { exec, pending } = useCommand()

async function resendVerify() {
  if (await exec(async () => { await auth.resendVerify(); return true })) {
    toast.add({ title: 'Письмо отправлено', description: `Ссылка — на ${auth.user?.email}.`, color: 'success', icon: 'i-lucide-mail-check' })
  }
}
</script>

<template>
  <UCard>
    <template #header>
      <div class="font-semibold text-highlighted">Аккаунт</div>
    </template>
    <div class="flex flex-wrap items-center gap-x-4 gap-y-3">
      <div class="min-w-0 flex-1">
        <div class="truncate font-medium text-highlighted">{{ auth.user?.email }}</div>
        <div class="mt-1">
          <UBadge
            v-if="auth.user?.emailVerified"
            color="success"
            variant="subtle"
            icon="i-lucide-mail-check"
            label="почта подтверждена"
          />
          <UBadge v-else color="warning" variant="subtle" icon="i-lucide-mail-warning" label="почта не подтверждена" />
        </div>
      </div>
      <UButton
        v-if="!auth.user?.emailVerified"
        label="Прислать письмо ещё раз"
        icon="i-lucide-send"
        color="neutral"
        variant="subtle"
        :loading="pending"
        @click="resendVerify"
      />
      <UButton label="Выйти" icon="i-lucide-log-out" color="neutral" variant="ghost" @click="auth.logout()" />
    </div>
  </UCard>
</template>
