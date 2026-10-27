<script setup lang="ts">
// Вход, регистрация и «забыли пароль» — в выдвижной панели поверх страницы: человек не теряет, где был.
const auth = useAuthStore()
const toast = useToast()
const { open, mode, next } = useAuthDrawer()
const { pending, error, run } = useAuthForm()

const form = reactive({ email: '', password: '', name: '' })
const sent = ref('')                               // «забыли пароль»: на какую почту ушла ссылка

const TITLES = { login: 'Вход', register: 'Регистрация', forgot: 'Новый пароль' }
const DESCRIPTIONS = {
  login: 'Рецепты, варки и пивоварня — после входа.',
  register: 'Бесплатно, нужна только почта.',
  forgot: 'Пришлём на почту ссылку, по которой можно задать новый пароль.',
}

watch([open, mode], () => {
  error.value = ''
  sent.value = ''
  form.password = ''
})

function validate(s: typeof form) {
  if (mode.value === 'forgot') return checkEmail(s.email)
  if (mode.value === 'register') return [...checkEmail(s.email), ...(s.name.trim() ? checkNick(s.name) : []), ...checkNewPassword(s.password)]
  return [...checkEmail(s.email), ...(s.password ? [] : [{ name: 'password', message: 'Введите пароль' }])]
}

async function done() {
  open.value = false
  if (next.value) await navigateTo(next.value)
}

async function submit() {
  if (mode.value === 'login') {
    if (await run(() => auth.login(form.email, form.password))) await done()
  } else if (mode.value === 'register') {
    if (!await run(() => auth.register(form.email, form.password, form.name))) return
    toast.add({
      title: 'Аккаунт создан',
      description: `Ссылка для подтверждения почты — в письме на ${auth.user?.email}.`,
      color: 'success',
      icon: 'i-lucide-mail-check',
    })
    await done()
  } else if (await run(() => auth.forgot(form.email))) {
    sent.value = form.email.trim()
  }
}
</script>

<template>
  <USlideover v-model:open="open" :title="TITLES[mode]" :description="DESCRIPTIONS[mode]" :ui="{ content: 'max-w-md' }">
    <template #body>
      <UAlert
        v-if="auth.unreachable"
        class="mb-6"
        color="error"
        variant="subtle"
        icon="i-lucide-server"
        title="Нет связи с сервисом"
        description="Попробуйте чуть позже."
      />
      <UAlert
        v-else-if="auth.expiredOn && mode === 'login'"
        class="mb-6"
        color="warning"
        variant="subtle"
        icon="i-lucide-lock"
        title="Вход истёк"
        description="Войдите снова — открытая страница и несохранённые правки останутся."
      />
      <div v-if="sent" class="space-y-6">
        <div class="flex gap-3">
          <UIcon name="i-lucide-mail-check" class="mt-0.5 size-5 shrink-0 text-primary" />
          <p class="text-default">
            Если <span class="font-medium text-highlighted">{{ sent }}</span> зарегистрирована, письмо со ссылкой для нового
            пароля уже там. Ссылка действует час.
          </p>
        </div>
        <UButton label="Ко входу" color="neutral" variant="subtle" size="lg" block @click="mode = 'login'" />
      </div>

      <UForm v-else :state="form" :validate="validate" :validate-on="['change']" class="space-y-5" @submit="submit">
        <UFormField label="Почта" name="email">
          <UInput v-model="form.email" type="email" autocomplete="email" size="lg" class="w-full" autofocus />
        </UFormField>
        <UFormField v-if="mode === 'register'" label="Ник" name="name" :help="NICK_OPTIONAL_HELP">
          <UInput v-model="form.name" autocomplete="nickname" size="lg" class="w-full" maxlength="24" />
        </UFormField>
        <UFormField
          v-if="mode !== 'forgot'"
          label="Пароль"
          name="password"
          :help="mode === 'register' ? `Не короче ${PASSWORD_MIN} символов` : undefined"
        >
          <template v-if="mode === 'login'" #hint>
            <UButton label="Забыли пароль?" variant="link" size="sm" class="p-0" @click="mode = 'forgot'" />
          </template>
          <AuthPassword v-model="form.password" :autocomplete="mode === 'register' ? 'new-password' : 'current-password'" />
        </UFormField>
        <UAlert v-if="error" color="error" variant="subtle" icon="i-lucide-circle-alert" :title="error" />
        <UButton
          type="submit"
          :label="{ login: 'Войти', register: 'Зарегистрироваться', forgot: 'Прислать ссылку' }[mode]"
          size="lg"
          block
          :loading="pending"
        />
      </UForm>
    </template>

    <template #footer>
      <p class="text-sm text-muted">
        <template v-if="mode === 'login'">
          Нет аккаунта?
          <UButton label="Зарегистрироваться" variant="link" class="p-0 font-medium" @click="mode = 'register'" />
        </template>
        <template v-else>
          {{ mode === 'register' ? 'Уже есть аккаунт?' : 'Вспомнили пароль?' }}
          <UButton label="Войти" variant="link" class="p-0 font-medium" @click="mode = 'login'" />
        </template>
      </p>
    </template>
  </USlideover>
</template>
