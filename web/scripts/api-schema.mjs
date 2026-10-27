// Выгрузить OpenAPI-схему сервиса в web/openapi.json — из неё npm run api:types генерирует типы.
// Python — из service/.venv, а если окружения нет — из PATH.
import { spawnSync } from 'node:child_process'
import { existsSync } from 'node:fs'
import { join, resolve } from 'node:path'

const web = resolve(import.meta.dirname, '..')
const service = resolve(web, '../service')
const windows = process.platform === 'win32'
const venv = join(service, '.venv', windows ? 'Scripts/python.exe' : 'bin/python')
const pythons = existsSync(venv) ? [venv] : windows ? ['python', 'python3'] : ['python3', 'python']

for (const python of pythons) {
  const run = spawnSync(python, ['-m', 'app', 'openapi', join(web, 'openapi.json')], { cwd: service, stdio: 'inherit' })
  if (run.error?.code === 'ENOENT') continue
  if (run.error) throw run.error
  process.exit(run.status ?? 1)
}
console.error('Python не найден: создайте service/.venv или поставьте python в PATH')
process.exit(1)
