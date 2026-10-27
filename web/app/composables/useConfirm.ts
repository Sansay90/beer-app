import { AppConfirmModal } from '#components'

type ConfirmOptions = InstanceType<typeof AppConfirmModal>['$props']

/** Спросить подтверждение модалкой и дождаться ответа: `if (await confirm({ title })) …` */
export function useConfirm() {
  const modal = useOverlay().create(AppConfirmModal)
  return async (options: ConfirmOptions) => (await modal.open(options)) === true
}
