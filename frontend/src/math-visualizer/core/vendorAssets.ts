const pendingAssets = new Map<string, Promise<void>>()

export function mathVendorUrl(file: string): string {
  const base = import.meta.env.BASE_URL.endsWith('/') ? import.meta.env.BASE_URL : `${import.meta.env.BASE_URL}/`
  return `${base}vendor/math-lab/${file}`
}

export function loadVendorScript(file: string): Promise<void> {
  const source = mathVendorUrl(file)
  const existing = pendingAssets.get(source)
  if (existing) return existing
  const request = new Promise<void>((resolve, reject) => {
    const loaded = document.querySelector<HTMLScriptElement>(`script[data-math-vendor="${file}"]`)
    if (loaded?.dataset.loaded === 'true') { resolve(); return }
    const script = loaded || document.createElement('script')
    script.src = source
    script.async = true
    script.dataset.mathVendor = file
    script.addEventListener('load', () => { script.dataset.loaded = 'true'; resolve() }, { once: true })
    script.addEventListener('error', () => { script.remove(); pendingAssets.delete(source); reject(new Error(`Unable to load ${file}.`)) }, { once: true })
    if (!loaded) document.head.append(script)
  })
  pendingAssets.set(source, request)
  return request
}

export function loadVendorStylesheet(file: string): Promise<void> {
  const source = mathVendorUrl(file)
  const existing = pendingAssets.get(source)
  if (existing) return existing
  const request = new Promise<void>((resolve, reject) => {
    const loaded = document.querySelector<HTMLLinkElement>(`link[data-math-vendor="${file}"]`)
    if (loaded?.dataset.loaded === 'true') { resolve(); return }
    const link = loaded || document.createElement('link')
    link.rel = 'stylesheet'
    link.href = source
    link.dataset.mathVendor = file
    link.addEventListener('load', () => { link.dataset.loaded = 'true'; resolve() }, { once: true })
    link.addEventListener('error', () => { link.remove(); pendingAssets.delete(source); reject(new Error(`Unable to load ${file}.`)) }, { once: true })
    if (!loaded) document.head.append(link)
  })
  pendingAssets.set(source, request)
  return request
}
