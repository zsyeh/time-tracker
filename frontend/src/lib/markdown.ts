import MarkdownIt from 'markdown-it'
import { escapeHtml } from 'markdown-it/lib/common/utils.mjs'
import type { RenderRule } from 'markdown-it/lib/renderer.mjs'
import DOMPurify from 'dompurify'
import { alert } from '@mdit/plugin-alert'
import { footnote } from '@mdit/plugin-footnote'
import { mark } from '@mdit/plugin-mark'
import { sub } from '@mdit/plugin-sub'
import { sup } from '@mdit/plugin-sup'
import { tasklist } from '@mdit/plugin-tasklist'
import { tex } from '@mdit/plugin-tex'
import katex from 'katex'
import hljs from 'highlight.js/lib/core'
import bash from 'highlight.js/lib/languages/bash'
import c from 'highlight.js/lib/languages/c'
import cpp from 'highlight.js/lib/languages/cpp'
import css from 'highlight.js/lib/languages/css'
import java from 'highlight.js/lib/languages/java'
import javascript from 'highlight.js/lib/languages/javascript'
import json from 'highlight.js/lib/languages/json'
import latex from 'highlight.js/lib/languages/latex'
import markdown from 'highlight.js/lib/languages/markdown'
import python from 'highlight.js/lib/languages/python'
import sql from 'highlight.js/lib/languages/sql'
import typescript from 'highlight.js/lib/languages/typescript'
import xml from 'highlight.js/lib/languages/xml'
import '@mdit/plugin-alert/style'
import 'highlight.js/styles/github-dark-dimmed.css'
import 'katex/dist/katex.min.css'
import './markdown.css'

for (const [name, language] of Object.entries({
  bash, c, cpp, css, java, javascript, json, latex, markdown, python, sql, typescript, xml,
})) hljs.registerLanguage(name, language)

const aliases: Record<string, string> = {
  cxx: 'cpp', html: 'xml', js: 'javascript', md: 'markdown', py: 'python',
  shell: 'bash', sh: 'bash', ts: 'typescript', tex: 'latex', vue: 'xml',
}

const md: MarkdownIt = new MarkdownIt({
  html: false,
  linkify: true,
  typographer: true,
  highlight(code, language) {
    const requested = aliases[language.toLowerCase()] || language.toLowerCase()
    if (requested && hljs.getLanguage(requested)) {
      return hljs.highlight(code, { language: requested, ignoreIllegals: true }).value
    }
    return escapeHtml(code)
  },
})
  .use(alert, { deep: true })
  .use(footnote)
  .use(mark)
  .use(sub)
  .use(sup)
  .use(tasklist, { disabled: true, label: true })
  .use(tex, {
    delimiters: 'all',
    mathFence: true,
    render(content, displayMode) {
      return katex.renderToString(content, {
        displayMode,
        output: 'htmlAndMathml',
        strict: 'warn',
        throwOnError: false,
        trust: false,
      })
    },
  })

const fallbackRender: RenderRule = (tokens, index, options, _env, self) => (
  self.renderToken(tokens, index, options)
)
const defaultLinkOpen: RenderRule = md.renderer.rules.link_open || fallbackRender
md.renderer.rules.link_open = (tokens, index, options, env, self) => {
  tokens[index].attrSet('target', '_blank')
  tokens[index].attrSet('rel', 'noopener noreferrer nofollow')
  return defaultLinkOpen(tokens, index, options, env, self)
}

const defaultImage: RenderRule = md.renderer.rules.image || fallbackRender
md.renderer.rules.image = (tokens, index, options, env, self) => {
  tokens[index].attrSet('loading', 'lazy')
  tokens[index].attrSet('decoding', 'async')
  tokens[index].attrSet('referrerpolicy', 'no-referrer')
  return defaultImage(tokens, index, options, env, self)
}

export function renderMarkdown(source: string): string {
  const rendered = md.render(source)
  return DOMPurify.sanitize(rendered, {
    USE_PROFILES: { html: true, svg: true, mathMl: true },
    ADD_ATTR: ['checked', 'decoding', 'disabled', 'loading', 'referrerpolicy', 'rel', 'target'],
    FORBID_TAGS: ['style'],
  })
}
