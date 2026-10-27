<script setup lang="ts">
// Фото пива крупно: листание стрелками и клавишами, подпись автора и лицензии чужого снимка.
// index — какое открыто (null — закрыто); to — ссылка «К рецепту»; removable — кнопка «Удалить» (событие remove).
import type { Photo } from '~/types'

const props = defineProps<{ photos: Photo[]; title?: string; to?: string; removable?: boolean }>()
const index = defineModel<number | null>('index', { default: null })
const emit = defineEmits<{ remove: [photo: Photo] }>()
const recipes = useRecipesStore()

const open = computed({
  get: () => index.value != null,
  set: (v) => { if (!v) index.value = null },
})
const shown = computed(() => (index.value == null ? null : props.photos[index.value] ?? null))
function step(d: number) {
  const n = props.photos.length
  if (index.value != null && n) index.value = (index.value + d + n) % n
}
onKeyStroke('ArrowLeft', () => open.value && step(-1))
onKeyStroke('ArrowRight', () => open.value && step(1))

const date = (p: Photo) => new Date(p.createdAt * 1000).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' })
</script>

<template>
  <UModal v-model:open="open" :title="title || 'Фото пива'" :ui="{ content: 'max-w-5xl overflow-hidden' }">
    <template #content>
      <div v-if="shown" class="relative bg-black">
        <img :src="recipes.photoUrl(shown.id)" alt="" class="mx-auto max-h-[78vh] w-auto object-contain">
        <template v-if="photos.length > 1">
          <UButton icon="i-lucide-chevron-left" color="neutral" variant="soft" class="absolute left-3 top-1/2 -translate-y-1/2 rounded-full" aria-label="Предыдущее" @click="step(-1)" />
          <UButton icon="i-lucide-chevron-right" color="neutral" variant="soft" class="absolute right-3 top-1/2 -translate-y-1/2 rounded-full" aria-label="Следующее" @click="step(1)" />
        </template>
        <UButton icon="i-lucide-x" color="neutral" variant="soft" class="absolute right-3 top-3 rounded-full" aria-label="Закрыть" @click="open = false" />
      </div>
      <div v-if="shown" class="flex items-center gap-3 px-4 py-3 text-sm">
        <div class="min-w-0">
          <div class="truncate">
            <span v-if="title" class="font-medium text-highlighted">{{ title }} · </span>
            <span class="num text-muted">{{ (index ?? 0) + 1 }} из {{ photos.length }} · {{ date(shown) }}</span>
          </div>
          <div v-if="shown.credit" class="truncate text-xs text-dimmed" :title="shown.credit">Фото: {{ shown.credit }}</div>
        </div>
        <span class="flex-1" />
        <UButton v-if="to" :to="to" label="К рецепту" trailing-icon="i-lucide-arrow-right" color="neutral" variant="ghost" size="sm" class="shrink-0" />
        <UButton v-if="removable" icon="i-lucide-trash-2" label="Удалить" color="error" variant="ghost" size="sm" class="shrink-0" @click="emit('remove', shown)" />
      </div>
    </template>
  </UModal>
</template>
