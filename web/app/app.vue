<script setup lang="ts">
import { ru } from '@nuxt/ui/locale'
</script>

<template>
  <UApp :locale="ru" :toaster="{ position: 'top-right', ui: { viewport: 'top-[4.5rem]' } }">
    <NuxtLayout>
      <NuxtPage />
    </NuxtLayout>
    <AuthDrawer />
  </UApp>
</template>
