<script setup lang="ts">
// Комментарий: автор (ник — ссылкой на его страницу), когда, текст; нравится / не нравится (за своё — нельзя),
// ответить, изменить своё, удалить своё (администратору — любое). Удалённый с ответами — «Комментарий удалён».
import type { Comment } from '~/types'

const props = defineProps<{ comment: Comment }>()
const emit = defineEmits<{ reply: []; vote: [pressed: 1 | -1]; save: [text: string]; remove: [] }>()

const editing = ref(false)
const draft = ref('')

function startEdit() {
  draft.value = props.comment.text
  editing.value = true
}

function save() {
  emit('save', draft.value.trim())
  editing.value = false
}
</script>

<template>
  <p v-if="comment.deleted" class="text-base text-dimmed italic">Комментарий удалён</p>
  <div v-else class="flex gap-3">
    <UserAvatar v-if="comment.author" :user="comment.author" class="size-9" />
    <div class="min-w-0 flex-1">
      <div class="flex flex-wrap items-baseline gap-x-2 text-sm">
        <NuxtLink v-if="comment.author?.name" :to="brewerPath(comment.author.name)" class="font-semibold text-highlighted hover:underline">
          {{ comment.author.name }}
        </NuxtLink>
        <span v-else class="font-semibold text-highlighted">{{ UNKNOWN_BREWER }}</span>
        <NuxtTime :datetime="comment.createdAt * 1000" relative locale="ru-RU" class="text-dimmed" />
        <span v-if="comment.edited" class="text-dimmed">изменён</span>
      </div>

      <div v-if="editing" class="mt-2 space-y-2">
        <UTextarea v-model="draft" autoresize :rows="2" :maxrows="12" size="lg" class="w-full" autofocus />
        <div class="flex gap-2">
          <UButton label="Сохранить" :disabled="!draft.trim()" @click="save" />
          <UButton label="Отмена" color="neutral" variant="ghost" @click="editing = false" />
        </div>
      </div>
      <p v-else class="mt-1 text-base break-words whitespace-pre-line text-default">{{ comment.text }}</p>

      <div v-if="!editing" class="mt-1.5 -ms-2 flex flex-wrap items-center gap-0.5">
        <UButton
          icon="i-lucide-thumbs-up"
          :label="String(comment.likes)"
          :color="comment.vote === 1 ? 'primary' : 'neutral'"
          variant="ghost"
          :disabled="comment.canEdit"
          :aria-pressed="comment.vote === 1"
          aria-label="Нравится"
          @click="emit('vote', 1)"
        />
        <UButton
          icon="i-lucide-thumbs-down"
          :label="String(comment.dislikes)"
          :color="comment.vote === -1 ? 'primary' : 'neutral'"
          variant="ghost"
          :disabled="comment.canEdit"
          :aria-pressed="comment.vote === -1"
          aria-label="Не нравится"
          @click="emit('vote', -1)"
        />
        <UButton label="Ответить" icon="i-lucide-reply" color="neutral" variant="ghost" @click="emit('reply')" />
        <UButton v-if="comment.canEdit" label="Изменить" icon="i-lucide-pencil" color="neutral" variant="ghost" @click="startEdit" />
        <UButton v-if="comment.canDelete" label="Удалить" icon="i-lucide-trash-2" color="neutral" variant="ghost" @click="emit('remove')" />
      </div>
    </div>
  </div>
</template>
