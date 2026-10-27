<script setup lang="ts">
defineProps<{ text: string }>()
</script>

<template>
  <p class="rounded-md border border-dashed border-default px-4 py-5 text-center text-sm text-muted">{{ text }}</p>
</template>
