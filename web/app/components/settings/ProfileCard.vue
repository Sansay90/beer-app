<script setup lang="ts">
// Профиль — то, что видят другие пивовары: аватар и ник. Почту не видит никто, кроме вас и администратора.
const auth = useAuthStore()
const { exec, pending } = useCommand()
const { pending: saving, error, run } = useAuthForm()

const input = ref<HTMLInputElement | null>(null)
const name = ref(auth.user?.name ?? '')
watch(() => auth.user?.name, (n) => { name.value = n ?? '' })
const changed = computed(() => !!name.value.trim() && name.value.trim() !== auth.user?.name)

async function pick(e: Event) {
  const el = e.target as HTMLInputElement
  const file = el.files?.[0]
  el.value = ''
  if (file) await exec(() => auth.setAvatar(file), 'Аватар обновлён')
}

async function save() {
  if (await run(() => auth.setName(name.value))) useToast().add({ title: 'Ник сохранён', color: 'success', icon: 'i-lucide-check' })
}
</script>

<template>
  <UCard v-if="auth.user">
    <template #header>
      <div class="font-semibold text-highlighted">Профиль</div>
      <p class="mt-1 text-sm text-muted">Так вас видят другие пивовары. Почту не видит никто. Без ника под рецептами — «{{ UNKNOWN_BREWER }}».</p>
    </template>

    <div class="flex flex-wrap items-center gap-5">
      <UserAvatar :user="auth.user" class="size-20" />
      <div class="flex flex-wrap gap-2">
        <UButton :label="auth.user.avatar ? 'Сменить фото' : 'Загрузить фото'" icon="i-lucide-camera" color="neutral" variant="outline" :loading="pending" @click="input?.click()" />
        <UButton v-if="auth.user.avatar" label="Убрать фото" icon="i-lucide-trash-2" color="neutral" variant="ghost" @click="exec(() => auth.removeAvatar(), 'Фото убрано')" />
      </div>
      <input ref="input" type="file" accept="image/jpeg,image/png,image/webp" class="hidden" @change="pick">
    </div>

    <UForm :state="{ name }" :validate="s => checkNick(s.name)" :validate-on="['change']" class="mt-6 space-y-4" @submit="save">
      <UFormField label="Ник" name="name" :help="NICK_HELP">
        <div class="flex flex-wrap gap-2">
          <UInput v-model="name" size="lg" maxlength="24" class="min-w-60 flex-1" />
          <UButton type="submit" label="Сохранить" size="lg" :disabled="!changed" :loading="saving" />
        </div>
      </UFormField>
      <UAlert v-if="error" color="error" variant="subtle" icon="i-lucide-circle-alert" :title="error" />
      <UButton v-if="auth.user.name" :to="brewerPath(auth.user.name)" label="Моя страница" icon="i-lucide-user" color="neutral" variant="link" class="px-0" />
    </UForm>
  </UCard>
</template>
