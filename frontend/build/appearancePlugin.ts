import type { Plugin } from 'vite'
// Build tooling only; the implementation deliberately uses Vite to compile pure TS.
// @ts-expect-error This local Node build module has no runtime application types.
import { appearanceArtifacts } from '../scripts/generate-appearance-bootstrap.mjs'
export function appearancePlugin(base: string): Plugin {
  return {
    name: 'learning-appearance-bootstrap',
    async buildStart() { await appearanceArtifacts() },
    transformIndexHtml: { order: 'post', async handler(html) {
      const { filename } = await appearanceArtifacts()
      return html.replace(/(<meta name="theme-color"[^>]*>)/, `$1\n    <script src="${base}${filename}"></script>`)
    } },
    async generateBundle() {
      const { filename, script } = await appearanceArtifacts()
      this.emitFile({ type: 'asset', fileName: filename, source: script })
    },
    configureServer(server) {
      server.middlewares.use(async (request, response, next) => {
        const { filename, script } = await appearanceArtifacts()
        if (request.url?.split('?')[0] !== `${base}${filename}`) return next()
        response.setHeader('Content-Type', 'text/javascript'); response.end(script)
      })
    },
  }
}
