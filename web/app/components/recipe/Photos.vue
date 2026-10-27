<script setup lang="ts">
// Фото пива по рецепту: лента снимков, добавление (уменьшается в браузере, utils/photo.ts), просмотр — PhotoViewer.
// У чужих снимков — подпись автора и лицензии (credit): её требуют свободные лицензии.
// editable — рецепт свой (добавить и удалить фото), moderate — администратор у чужого (только удалить).
import type { Photo } from '~/types'

const props = defineProps<{ recipeId: string; editable?: boolean; moderate?: boolean }>()
const { $api } = useNuxtApp()
const photoUrl = usePhotoUrl()
const { exec } = useCommand()
const confirm = useConfirm()

const rid = toRef(() => props.recipeId)
const { data: photos, error } = useApi('/api/recipes/{rid}/photos', { path: { rid }, key: () => `photos:${rid.value}`, default: () => [] })
useErrorToast(error)
const uploading = ref(0)
const input = ref<HTMLInputElement | null>(null)
const current = ref<number | null>(null)                 // открытое крупно

/** Тело запроса — сама картинка, уменьшенная shrinkPhoto. */
async function upload(file: File) {
  const image = await shrinkPhoto(file)
  return $api('/api/recipes/{rid}/photos', {
    method: 'POST',
    path: { rid: props.recipeId },
    body: image as unknown as string,
    headers: { 'Content-Type': image.type },
  })
}

async function add(e: Event) {
  const el = e.target as HTMLInputElement
  const files = [...(el.files ?? [])]
  el.value = ''
  for (const file of files) {
    uploading.value++
    const photo = await exec(() => upload(file))
    uploading.value--
    if (photo) photos.value = [...photos.value, photo]
  }
}

async function remove(p: Photo) {
  const ok = await confirm({ title: 'Удалить фото?', description: 'Снимок пропадёт из рецепта.', confirmLabel: 'Удалить', color: 'error' })
  if (!ok || !await exec(() => $api('/api/photos/{pid}', { method: 'DELETE', path: { pid: p.id } }), 'Фото удалено')) return
  photos.value = photos.value.filter(x => x.id !== p.id)
  current.value = photos.value.length ? Math.min(current.value ?? 0, photos.value.length - 1) : null
}

const credits = computed(() => photos.value.map(p => p.credit).filter((c): c is string => !!c))
</script>

<template>
  <div v-if="editable || photos.length">
    <div class="flex gap-3 overflow-x-auto pb-1">
      <button
        v-for="(p, i) in photos"
        :key="p.id"
        type="button"
        class="group/photo relative aspect-4/3 h-32 shrink-0 overflow-hidden rounded-lg bg-elevated ring ring-default focus-visible:outline-2 focus-visible:outline-primary"
        :title="p.credit ? `Фото: ${p.credit}` : undefined"
        :aria-label="`Фото ${i + 1}`"
        @click="current = i"
      >
        <img :src="photoUrl(p.id, true)" alt="" loading="lazy" class="size-full object-cover transition duration-300 group-hover/photo:scale-105">
      </button>
      <div v-for="n in uploading" :key="`up-${n}`" class="grid aspect-4/3 h-32 shrink-0 place-items-center rounded-lg bg-elevated">
        <UIcon name="i-lucide-loader-circle" class="size-5 animate-spin text-muted" />
      </div>
      <button
        v-if="editable"
        type="button"
        class="flex aspect-4/3 h-32 shrink-0 flex-col items-center justify-center gap-1.5 rounded-lg border border-dashed border-accented text-sm text-muted transition hover:border-primary hover:text-highlighted focus-visible:outline-2 focus-visible:outline-primary"
        @click="input?.click()"
      >
        <UIcon name="i-lucide-camera" class="size-5" />
        Добавить фото
      </button>
      <input v-if="editable" ref="input" type="file" accept="image/jpeg,image/png,image/webp" multiple class="hidden" @change="add">
    </div>
    <p v-if="credits.length" class="mt-1.5 truncate text-[11px] text-dimmed" :title="credits.join('; ')">Фото: {{ credits.join('; ') }}</p>

    <RecipePhotoViewer v-model:index="current" :photos="photos" :removable="editable || moderate" @remove="remove" />
  </div>
</template>
