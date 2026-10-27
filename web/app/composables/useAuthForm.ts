import type { FormError } from '@nuxt/ui'

const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/
export const PASSWORD_MIN = 8

/** Форма входа: ошибка — текстом над кнопкой, а не всплывающим сообщением, чтобы её было видно при исправлении. */
export function useAuthForm() {
  const pending = ref(false)
  const error = ref('')

  async function run(action: () => Promise<unknown>) {
    pending.value = true
    error.value = ''
    try {
      await action()
      return true
    } catch (e) {
      const text = isOffline(e) ? 'нет связи с сервисом' : errorText(e)
      error.value = text.charAt(0).toUpperCase() + text.slice(1)
      return false
    } finally {
      pending.value = false
    }
  }

  return { pending, error, run }
}

export function checkEmail(email: string): FormError[] {
  return EMAIL.test(email.trim()) ? [] : [{ name: 'email', message: 'Похоже, в адресе ошибка' }]
}

export function checkNewPassword(password: string): FormError[] {
  return password.length >= PASSWORD_MIN ? [] : [{ name: 'password', message: `Не короче ${PASSWORD_MIN} символов` }]
}
