<script setup lang="ts">
import { ru } from '@nuxt/ui/locale'

// заголовок вкладки и превью ссылок: страница задаёт своё название, сайт — дописывается
const SITE_NAME = 'Пивоварня'
useSeoMeta({ titleTemplate: t => (t && t !== SITE_NAME ? `${t} — ${SITE_NAME}` : SITE_NAME), ogSiteName: SITE_NAME, ogLocale: 'ru_RU' })
</script>

<template>
  <UApp :locale="ru" :toaster="{ position: 'top-right', ui: { viewport: 'top-[4.5rem]' } }">
    <NuxtLayout>
      <NuxtPage />
    </NuxtLayout>
    <AuthDrawer />
  </UApp>
</template>
