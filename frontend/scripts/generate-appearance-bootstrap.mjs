import { build } from 'vite'
import { createHash } from 'node:crypto'
import { readFile, mkdir, writeFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { resolve } from 'node:path'
const project = fileURLToPath(new URL('..', import.meta.url))
let promise
async function bundle(entry, format) {
  const result = await build({ configFile: false, publicDir: false, logLevel: 'silent', build: { write: false, minify: 'esbuild', lib: { entry: resolve(project, entry), formats: [format], name: 'LearningAppearanceBootstrap' } } })
  const output = (Array.isArray(result) ? result[0] : result).output.find((item) => item.type === 'chunk')
  return output.code
}
export function appearanceArtifacts() {
  return promise ||= (async () => {
    const [script, paletteModule, tokens] = await Promise.all([bundle('shared/appearance/bootstrap.ts', 'iife'), bundle('shared/appearance/palette.ts', 'es'), readFile(resolve(project, 'shared/design/tokens.css'), 'utf8')])
    const palette = await import(`data:text/javascript;base64,${Buffer.from(paletteModule).toString('base64')}`)
    const css = `${tokens}\n${palette.paletteCss()}\n`
    const hash = createHash('sha256').update(script).digest('hex').slice(0, 12)
    const staticDir = resolve(project, '../tracker/static/tracker/ui')
    await mkdir(staticDir, { recursive: true })
    await Promise.all([writeFile(resolve(staticDir, 'appearance-bootstrap.js'), script), writeFile(resolve(staticDir, 'tokens.css'), css)])
    return { script, css, filename: `assets/appearance.${hash}.js` }
  })()
}
if (process.argv[1] === fileURLToPath(import.meta.url)) await appearanceArtifacts()
