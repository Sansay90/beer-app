// Фото перед загрузкой: уменьшается до 1600 px по длинной стороне и пережимается в JPEG.
// Пережатие заодно убирает EXIF — с телефона там бывают координаты съёмки.
export const PHOTO_MAX_SIDE = 1600

export async function shrinkPhoto(file: File, max = PHOTO_MAX_SIDE, quality = 0.85): Promise<Blob> {
  let bitmap: ImageBitmap
  try {
    bitmap = await createImageBitmap(file, { imageOrientation: 'from-image' })
  } catch {
    throw new Error(`«${file.name}» не открылось — нужен JPEG, PNG или WebP`)
  }
  const k = Math.min(1, max / Math.max(bitmap.width, bitmap.height))
  const canvas = document.createElement('canvas')
  canvas.width = Math.round(bitmap.width * k)
  canvas.height = Math.round(bitmap.height * k)
  canvas.getContext('2d')!.drawImage(bitmap, 0, 0, canvas.width, canvas.height)
  bitmap.close()
  return new Promise((resolve, reject) =>
    canvas.toBlob(b => (b ? resolve(b) : reject(new Error('Не получилось обработать фото'))), 'image/jpeg', quality))
}
