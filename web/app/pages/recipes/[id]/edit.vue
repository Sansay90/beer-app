<script setup lang="ts">
definePageMeta({ auth: 'user', teaser: 'recipe', title: 'Правка рецепта' })

const route = useRoute()
const id = computed(() => route.params.id as string)
</script>

<template>
  <RecipeEditor :id="id" />
</template>
