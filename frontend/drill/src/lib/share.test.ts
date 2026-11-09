// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { post } from './api'
import { createAndCopyShareOnGesture } from './share'

vi.mock('./api', () => ({ post: vi.fn() }))

describe('page-turn share copying', () => {
  beforeEach(() => vi.clearAllMocks())

  it('starts a clipboard write during the click and resolves the destination URL later', async () => {
    let resolveEndpoint!: (value: string) => void
    const endpoint = new Promise<string>((resolve) => { resolveEndpoint = resolve })
    const copied: Array<Record<string, Promise<Blob>>> = []
    class TestClipboardItem {
      constructor(public data: Record<string, Promise<Blob>>) { copied.push(data) }
    }
    Object.defineProperty(window, 'ClipboardItem', { configurable: true, value: TestClipboardItem })
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { write: vi.fn().mockResolvedValue(undefined) },
    })
    vi.mocked(post).mockResolvedValue({ share_url: 'https://drill.ehzsy.site/share/q/token/', markdown_url: '' })

    const result = createAndCopyShareOnGesture(endpoint)
    expect(navigator.clipboard.write).toHaveBeenCalledTimes(1)
    expect(post).not.toHaveBeenCalled()
    resolveEndpoint('/api/drill/questions/example/share/')
    const blob = await copied[0]['text/plain']
    const text = await new Promise<string>((resolve) => {
      const reader = new FileReader()
      reader.onload = () => resolve(String(reader.result))
      reader.readAsText(blob)
    })
    expect(text).toBe('https://drill.ehzsy.site/share/q/token/')
    expect((await result).copied).toBe(true)
  })
})
