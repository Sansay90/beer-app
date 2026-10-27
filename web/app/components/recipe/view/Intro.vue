<script setup lang="ts">
// Шапка рецепта: бокал, название, стиль, автор (у чужого), описание, фото пива; внизу — отклик: нравится,
// не нравится, обсуждение, сколько раз сварили. Признаки — видимость, избранное,
// «в пивоварне» — в верхней строке страницы (view/Actions.vue).
import type { RecipeDetail } from '~/types'
import { NuxtLink } from '#components'

const props = defineProps<{ recipe: RecipeDetail; recipeId: string; ebc?: number | null }>()

const meta = computed(() => props.recipe.meta)
const { vote } = useRecipeVote()

// отклик: голоса, обсуждение, сколько раз сварили все
const commentsLabel = computed(() => {
  const n = meta.value.comments
  return n ? `${n} ${plural(n, 'комментарий', 'комментария', 'комментариев')}` : 'Обсудить'
})
const brewsLabel = computed(() => {
  const n = meta.value.brewsTotal
  return n ? `Сварили ${n} ${plural(n, 'раз', 'раза', 'раз')}` : 'Ещё не варили'
})
</script>

<template>
  <UCard :ui="{ body: 'p-5 sm:p-6' }">
    <div class="flex items-center gap-4">
      <RecipeGlass :ebc="ebc" :style-code="recipe.style?.code" class="h-20" />
      <div class="min-w-0">
        <h1 class="truncate text-3xl font-semibold text-highlighted">{{ recipe.name }}</h1>
        <div class="truncate text-muted">{{ styleLabel(recipe.style) }}</div>
        <component
          :is="meta.author.name ? NuxtLink : 'div'"
          v-if="!meta.mine"
          :to="meta.author.name ? brewerPath(meta.author.name) : undefined"
          class="mt-1.5 flex w-fit max-w-full items-center gap-2 text-muted"
          :class="meta.author.name && 'hover:text-highlighted'"
        >
          <UserAvatar :user="meta.author" class="size-7" />
          <span class="truncate">автор <span class="font-medium text-highlighted">{{ brewerName(meta.author) }}</span></span>
        </component>
      </div>
    </div>
    <RecipeDescription v-if="recipe.notes" :text="recipe.notes" class="mt-5 max-w-3xl" />
    <RecipePhotos :recipe-id="recipeId" :editable="meta.canEdit" :moderate="meta.canModerate" class="mt-5" />

    <div class="mt-5 flex flex-wrap items-center gap-2 border-t border-default pt-4">
      <!-- за свой рецепт не голосуют — кнопки показывают счёт -->
      <UButton
        icon="i-lucide-thumbs-up"
        :label="String(meta.likes)"
        :color="meta.vote === 1 ? 'primary' : 'neutral'"
        :variant="meta.vote === 1 ? 'soft' : 'outline'"
        size="lg"
        :disabled="meta.mine"
        :aria-pressed="meta.vote === 1"
        aria-label="Нравится"
        @click="vote(recipeId, meta, 1)"
      />
      <UButton
        icon="i-lucide-thumbs-down"
        :label="String(meta.dislikes)"
        :color="meta.vote === -1 ? 'primary' : 'neutral'"
        :variant="meta.vote === -1 ? 'soft' : 'outline'"
        size="lg"
        :disabled="meta.mine"
        :aria-pressed="meta.vote === -1"
        aria-label="Не нравится"
        @click="vote(recipeId, meta, -1)"
      />
      <UButton icon="i-lucide-message-circle" :label="commentsLabel" color="neutral" variant="ghost" size="lg" to="#comments" />
      <span class="flex items-center gap-1.5 px-2 text-base text-muted">
        <UIcon name="i-lucide-beer" class="size-5" />{{ brewsLabel }}
      </span>
    </div>
  </UCard>
</template>
