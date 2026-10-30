<script setup lang="ts">
// «Партия вылита» — веха журнала, причина — по желанию. Партия остаётся в «Моих варках» с меткой, напоминания
// прекращаются, в «сварили N раз» не идёт (logbook.py). Передумали — удалить запись в журнале.
const props = defineProps<{ brewId: string }>()
const open = defineModel<boolean>('open', { default: false })
const emit = defineEmits<{ done: [] }>()
const { $api } = useNuxtApp()
const { exec, pending } = useCommand()

const reason = ref('')
watch(open, (o) => { if (o) reason.value = '' })

async function save() {
  const entry = await exec(() => $api('/api/brews/{bid}/entries', { method: 'POST', path: { bid: props.brewId }, body: { kind: 'dumped', text: reason.value.trim() || null } }))
  if (!entry) return
  open.value = false
  emit('done')
}
</script>

<template>
  <UModal v-model:open="open" title="Партия вылита?" description="Варка останется в журнале с пометкой, напоминания прекратятся.">
    <template #body>
      <UFormField label="Причина" hint="необязательно">
        <UTextarea v-model="reason" autoresize :rows="2" :maxrows="6" maxlength="2000" placeholder="Заражение, посторонний запах…" size="lg" class="w-full" />
      </UFormField>
    </template>
    <template #footer>
      <div class="flex w-full justify-end gap-2">
        <UButton label="Отмена" color="neutral" variant="ghost" size="lg" @click="open = false" />
        <UButton label="Вылито" icon="i-lucide-circle-x" color="error" size="lg" :loading="pending" @click="save" />
      </div>
    </template>
  </UModal>
</template>
