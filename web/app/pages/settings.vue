<script setup lang="ts">
import type { Equipment, SettingsUpdate } from '~/types'

const brewery = useBreweryStore()
const { $bridgeUrl } = useNuxtApp()
const { enabled: soundOn, toggle: toggleSound, play } = useSound()
const { exec, pending } = useCommand()
const push = usePush()
const prefs = usePreferencesStore()
const GRAVITY_UNITS = [
  { label: '°P — Плато', value: 'plato' },
  { label: 'SG — удельная плотность', value: 'sg' },
]
const pushCmd = useCommand()

function togglePush(on: boolean) {
  pushCmd.exec(() => (on ? push.enable() : push.disable()))
}

// форма калибровки: заполняется значениями пивоварни, пока человек её не трогал
const form = reactive<Required<SettingsUpdate>>({ calibration: 0, boilCompensation: 0 })
const device = computed(() => brewery.snapshot?.settings)
const changed = computed(() => !!device.value && (form.calibration !== device.value.calibration || form.boilCompensation !== device.value.boilCompensation))

function reset() {
  form.calibration = device.value?.calibration ?? 0
  form.boilCompensation = device.value?.boilCompensation ?? 0
}
watchOnce(() => device.value?.calibration != null, reset, { immediate: true })

// профиль оборудования: форма — копия сохранённого, пока человек её не трогал
const equipment = useEquipmentStore()
const eqCmd = useCommand()
const eqForm = ref<Equipment | null>(null)
const eqChanged = computed(() => !!eqForm.value && JSON.stringify(eqForm.value) !== JSON.stringify(equipment.value))
function resetEquipment() {
  eqForm.value = equipment.value ? { ...equipment.value } : null
}
onMounted(async () => {
  if (!equipment.value) await eqCmd.exec(equipment.fetch)
  resetEquipment()
})
async function saveEquipment() {
  if (eqForm.value && await eqCmd.exec(() => equipment.save(eqForm.value!), 'Профиль оборудования сохранён')) resetEquipment()
}

const EQUIPMENT_FIELDS: { key: keyof Equipment; label: string; unit: string; step: number; description: string }[] = [
  { key: 'efficiency', label: 'Эффективность', unit: '%', step: 1, description: 'Для новых рецептов.' },
  { key: 'evaporation', label: 'Испарение', unit: 'л/ч', step: 0.1, description: 'За час кипячения без крышки.' },
]

const connection = computed(() => [
  {
    label: 'Посредник',
    badge: brewery.connected
      ? { color: 'success' as const, icon: 'i-lucide-server', label: `на связи · ${$bridgeUrl}` }
      : { color: 'error' as const, icon: 'i-lucide-circle-x', label: 'нет связи' },
  },
  {
    label: 'Пивоварня',
    badge: brewery.online
      ? { color: 'success' as const, icon: 'i-lucide-wifi', label: 'в сети' }
      : { color: 'warning' as const, icon: 'i-lucide-wifi-off', label: 'не в сети' },
  },
])
</script>

<template>
  <UDashboardPanel id="settings">
    <template #header>
      <UDashboardNavbar title="Настройки">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="mx-auto w-full max-w-3xl space-y-6">
        <UCard>
          <template #header>
            <div class="font-semibold text-highlighted">Подключение</div>
          </template>
          <dl class="grid grid-cols-1 gap-x-6 gap-y-4 sm:grid-cols-[12rem_1fr]">
            <template v-for="c in connection" :key="c.label">
              <dt class="text-sm text-muted">{{ c.label }}</dt>
              <dd><UBadge variant="subtle" v-bind="c.badge" /></dd>
            </template>
            <dt class="text-sm text-muted">Модель</dt>
            <dd class="text-sm">
              <span class="font-medium text-highlighted">{{ device?.model ? `B${device.model}` : '—' }}</span>
              <span class="text-muted"> · заводская настройка, только просмотр</span>
            </dd>
            <dt class="text-sm text-muted">Потолок мощности</dt>
            <dd class="num text-sm font-medium text-highlighted">{{ fmtWatts(device?.maxWatts) }}</dd>
          </dl>
        </UCard>

        <UCard>
          <template #header>
            <div class="font-semibold text-highlighted">Калибровка датчика</div>
          </template>
          <div class="space-y-6">
            <UFormField
              label="Калибровка температуры"
              description="Поправка к показаниям датчика, −10…+10 °C. Подбирается по эталонному термометру."
              hint="°C"
            >
              <UInputNumber
                v-model="form.calibration"
                :min="-10"
                :max="10"
                :step="0.1"
                :step-snapping="false"
                :format-options="{ minimumFractionDigits: 1, maximumFractionDigits: 1 }"
                class="w-48"
              />
            </UFormField>
            <UFormField
              label="Компенсация температуры кипения"
              description="Действует выше 90 °C, 0…10 °C. Нужна, если по датчику вода кипит заметно ниже 100 °C и таймер кипячения не стартует."
              hint="°C"
            >
              <UInputNumber
                v-model="form.boilCompensation"
                :min="0"
                :max="10"
                :step="0.1"
                :step-snapping="false"
                :format-options="{ minimumFractionDigits: 1, maximumFractionDigits: 1 }"
                class="w-48"
              />
            </UFormField>
          </div>
          <template #footer>
            <div class="flex justify-end gap-2">
              <UButton color="neutral" variant="ghost" label="Сбросить" :disabled="!changed" @click="reset" />
              <UButton
                icon="i-lucide-save"
                label="Записать в пивоварню"
                :loading="pending"
                :disabled="!changed || !brewery.online"
                @click="exec(() => brewery.saveSettings({ ...form }), 'Калибровка записана в пивоварню')"
              />
            </div>
          </template>
        </UCard>

        <UCard id="equipment">
          <template #header>
            <div class="font-semibold text-highlighted">Оборудование</div>
            <div class="text-sm text-muted">Эффективность подставляется в новые рецепты, по испарению считается промывочная вода. Не знаете своих цифр — оставьте средние и поправьте после пары варок.</div>
          </template>
          <div v-if="eqForm" class="grid gap-x-6 gap-y-5 sm:grid-cols-2">
            <UFormField v-for="f in EQUIPMENT_FIELDS" :key="f.key" :label="f.label" :hint="f.unit" :description="f.description">
              <UInputNumber
                v-model="eqForm[f.key]"
                :min="0"
                :step="f.step"
                :step-snapping="false"
                :format-options="{ maximumFractionDigits: 2 }"
                placeholder="—"
                class="w-full"
              />
            </UFormField>
          </div>
          <template #footer>
            <div class="flex justify-end gap-2">
              <UButton color="neutral" variant="ghost" label="Сбросить" :disabled="!eqChanged" @click="resetEquipment" />
              <UButton icon="i-lucide-save" label="Сохранить" :loading="eqCmd.pending.value" :disabled="!eqChanged" @click="saveEquipment" />
            </div>
          </template>
        </UCard>

        <UCard>
          <template #header>
            <div class="font-semibold text-highlighted">Уведомления</div>
            <div class="text-sm text-muted">Подсказки, закладки и конец программы — даже когда приложение закрыто. Настраивается для каждого устройства отдельно.</div>
          </template>
          <div class="flex flex-wrap items-center justify-between gap-4">
            <USwitch
              :model-value="push.state.value === 'on'"
              :disabled="push.state.value === 'unsupported' || push.state.value === 'denied'"
              :loading="pushCmd.pending.value"
              label="Системные уведомления"
              @update:model-value="togglePush"
            />
            <UButton
              color="neutral"
              variant="outline"
              icon="i-lucide-send"
              label="Проверить"
              :disabled="push.state.value !== 'on'"
              @click="pushCmd.exec(push.test, 'Уведомление отправлено')"
            />
          </div>
          <p v-if="push.state.value === 'denied'" class="mt-3 text-sm text-warning">
            Уведомления для этого сайта запрещены — разрешите их в настройках браузера.
          </p>
          <p v-else-if="push.state.value === 'unsupported'" class="mt-3 text-sm text-muted">
            Этот браузер не поддерживает уведомления.
          </p>
        </UCard>

        <UCard>
          <template #header>
            <div class="font-semibold text-highlighted">Единицы</div>
            <div class="text-sm text-muted">Как показывать плотность в рецептах. Настраивается для каждого устройства отдельно.</div>
          </template>
          <UFormField label="Плотность">
            <URadioGroup v-model="prefs.gravityUnit" :items="GRAVITY_UNITS" orientation="horizontal" />
          </UFormField>
        </UCard>

        <UCard>
          <template #header>
            <div class="font-semibold text-highlighted">Звук</div>
            <div class="text-sm text-muted">Подсказки, закладки и конец программы. Настраивается для каждого устройства отдельно.</div>
          </template>
          <div class="flex flex-wrap items-center justify-between gap-4">
            <USwitch :model-value="soundOn" label="Звуковые оповещения" @update:model-value="toggleSound" />
            <div class="flex flex-wrap gap-2">
              <UButton color="neutral" variant="outline" icon="i-lucide-bell-ring" label="Подсказка" :disabled="!soundOn" @click="play('alert')" />
              <UButton color="neutral" variant="outline" icon="i-lucide-bell-ring" label="Закладка" :disabled="!soundOn" @click="play('addition')" />
              <UButton color="neutral" variant="outline" icon="i-lucide-flag" label="Конец" :disabled="!soundOn" @click="play('end')" />
            </div>
          </div>
        </UCard>
      </div>
    </template>
  </UDashboardPanel>
</template>
