// Модульные тесты чистых утилит (app/utils) — без Nuxt: утилиты импортируют друг друга явно.
// Псевдонимы — как у Nuxt: ~ и @ — app/, ~~ и @@ — корень web/.
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vitest/config'

const app = fileURLToPath(new URL('./app', import.meta.url))
const root = fileURLToPath(new URL('.', import.meta.url))

export default defineConfig({
  resolve: {
    alias: { '~~': root, '@@': root, '~': app, '@': app },
  },
  test: {
    include: ['test/unit/**/*.test.ts'],
  },
})
