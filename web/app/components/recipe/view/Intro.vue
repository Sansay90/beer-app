<script setup lang="ts">
// Шапка рецепта: бокал, название, стиль, автор или видимость, описание, фото пива.
import type { RecipeDetail } from '~/types'
import { NuxtLink } from '#components'

const props = defineProps<{ recipe: RecipeDetail; recipeId: string; ebc?: number | null }>()

const meta = computed(() => props.recipe.meta)
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
