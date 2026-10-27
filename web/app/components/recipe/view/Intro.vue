<script setup lang="ts">
// Шапка рецепта: бокал, название, стиль, автор или видимость, описание, фото пива.
import type { RecipeDetail } from '~/types'

const props = defineProps<{ recipe: RecipeDetail; recipeId: string; ebc?: number | null }>()

const meta = computed(() => props.recipe.meta)
</script>

<template>
  <UCard :ui="{ body: 'p-5 sm:p-6' }">
    <div class="flex items-center gap-4">
      <RecipeGlass :ebc="ebc" :style-code="recipe.style?.code" class="h-20" />
      <div class="min-w-0">
        <h1 class="truncate text-2xl font-semibold text-highlighted">{{ recipe.name }}</h1>
        <div class="truncate text-muted">{{ styleLabel(recipe.style) }}</div>
        <div v-if="!meta.mine" class="mt-1 truncate text-sm text-muted">
          автор <span class="font-medium text-highlighted">{{ meta.author }}</span>
        </div>
        <UBadge
          v-else
          class="mt-2"
          color="neutral"
          variant="subtle"
          size="sm"
          :icon="meta.visibility === 'public' ? 'i-lucide-globe' : 'i-lucide-lock'"
          :label="meta.visibility === 'public' ? 'опубликован' : 'виден только вам'"
        />
      </div>
    </div>
    <RecipeDescription v-if="recipe.notes" :text="recipe.notes" class="mt-5 max-w-3xl" />
    <RecipePhotos :recipe-id="recipeId" :editable="meta.canEdit" :moderate="meta.canModerate" class="mt-5" />
  </UCard>
</template>
