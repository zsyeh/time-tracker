import { uiText } from './uiText'
export type ClipboardImageResult = { blob: Blob; combined: boolean; limited: boolean }

export function fittedCanvasSize(
  images: Array<{ width: number; height: number }>,
  maxWidth = 8192,
  maxHeight = 16384,
  requestedScale = 1,
  maxPixels = Infinity,
) {
  const width = Math.max(...images.map((image) => image.width), 1)
  const height = images.reduce((sum, image) => sum + image.height * (width / image.width), 0)
  const scale = Math.min(requestedScale, maxWidth / width, maxHeight / height, Math.sqrt(maxPixels / (width * height)))
  return {
    width: Math.max(1, Math.floor(width * scale)),
    height: Math.max(1, Math.floor(height * scale)),
    scale,
  }
}

async function decodeBlob(blob: Blob): Promise<ImageBitmap> {
  if ('createImageBitmap' in window) return createImageBitmap(blob)
  const url = URL.createObjectURL(blob)
  try {
    const image = new Image()
    image.src = url
    await image.decode()
    return image as unknown as ImageBitmap
  } finally {
    URL.revokeObjectURL(url)
  }
}

function canvasBlob(canvas: HTMLCanvasElement): Promise<Blob> {
  return new Promise((resolve, reject) => canvas.toBlob(
    (blob) => blob ? resolve(blob) : reject(new Error(uiText("浏览器无法生成 PNG 图片。"))),
    'image/png',
  ))
}

export async function buildClipboardPng(urls: string[], requestedScale = 1): Promise<ClipboardImageResult> {
  if (!Number.isFinite(requestedScale) || requestedScale < 1 || requestedScale > 8) throw new Error('Invalid image copy scale.')
  if (!urls.length) throw new Error(uiText("当前题目没有可复制的题图。"))
  const blobs = await Promise.all(urls.map(async (url) => {
    const response = await fetch(url, { credentials: 'same-origin' })
    if (!response.ok) throw new Error(`题图读取失败（HTTP ${response.status}）。`)
    return response.blob()
  }))
  if (requestedScale === 1 && blobs.length === 1 && blobs[0].type === 'image/png') {
    return { blob: blobs[0], combined: false, limited: false }
  }
  const images = await Promise.all(blobs.map(decodeBlob))
  try {
    // Upscaled exports have a 16MP budget (64MiB RGBA canvas), independent
    // of display density; retain the existing 1× PNG passthrough.
    const size = fittedCanvasSize(images, 8192, 16384, requestedScale, requestedScale > 1 ? 16 * 1024 * 1024 : Infinity)
    const canvas = document.createElement('canvas')
    canvas.width = size.width
    canvas.height = size.height
    const context = canvas.getContext('2d')
    if (!context) throw new Error(uiText("浏览器无法创建题图画布。"))
    context.imageSmoothingEnabled = true
    context.imageSmoothingQuality = 'high'
    context.fillStyle = '#ffffff'
    context.fillRect(0, 0, canvas.width, canvas.height)
    let y = 0, sourceY = 0
    for (const image of images) {
      const width = size.width
      sourceY += image.height * (width / image.width)
      const bottom = Math.min(size.height, Math.round(sourceY))
      context.drawImage(image, 0, y, width, bottom - y)
      y = bottom
    }
    return { blob: await canvasBlob(canvas), combined: blobs.length > 1, limited: size.scale < requestedScale - 1e-9 }
  } finally {
    images.forEach((image) => image.close?.())
  }
}

export async function copyImagesToClipboard(urls: string[] | Promise<string[]>, requestedScale = 1): Promise<ClipboardImageResult> {
  const ClipboardItemConstructor = window.ClipboardItem
  if (!navigator.clipboard?.write || !ClipboardItemConstructor) {
    throw new Error(uiText("此浏览器不支持直接复制图片，请使用系统分享或下载。"))
  }
  // Keep the Blob promise inside ClipboardItem. Safari uses this to retain the
  // original button activation while authenticated images are fetched.
  const pngPromise = Promise.resolve(urls).then(resolved => buildClipboardPng(resolved, requestedScale))
  const blobPromise = pngPromise.then((result) => result.blob)
  void blobPromise.catch(() => { /* The clipboard write may fail before media finishes loading. */ })
  await navigator.clipboard.write([new ClipboardItemConstructor({
    'image/png': blobPromise,
  })])
  return pngPromise
}

export async function shareImageBlob(blob: Blob, filename: string) {
  const file = new File([blob], filename, { type: 'image/png' })
  if (!navigator.share || (navigator.canShare && !navigator.canShare({ files: [file] }))) {
    throw new Error(uiText("此浏览器不支持图片系统分享，请下载后使用。"))
  }
  await navigator.share({ files: [file], title: uiText("题目图片") })
}

export function downloadImageBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}
