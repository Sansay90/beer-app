<script setup lang="ts">
// /recipes/new?from=<id> — копия существующего рецепта
definePageMeta({ auth: 'user', teaser: 'recipe', title: 'Новый рецепт' })

const route = useRoute()
const from = computed(() => (route.query.from as string | undefined) ?? null)
</script>

<template>
  <RecipeEditor :id="null" :from="from" />
</template>
