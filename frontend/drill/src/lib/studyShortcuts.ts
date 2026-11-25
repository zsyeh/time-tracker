export type StudyShortcut = 'previous' | 'next' | 'favorite' | 'review' | 'mastered' | 'preview' | 'undo' | 'answer' | 'fullscreen' | 'exit'
const bindings: Record<string, StudyShortcut> = { arrowleft:'previous',arrowright:'next',f:'favorite',n:'review',m:'mastered',q:'preview',u:'undo',a:'answer',p:'fullscreen',x:'exit' }
export function installStudyShortcuts(actions: Partial<Record<StudyShortcut, () => unknown>>, options: { blocked?: () => boolean; error?: (reason: unknown) => void; feedback?: (action: StudyShortcut) => void } = {}) {
  function keydown(event: KeyboardEvent) {
    if (event.defaultPrevented || event.repeat || event.isComposing || event.keyCode === 229 || event.ctrlKey || event.altKey || event.metaKey) return
    const key=event.key.toLowerCase(),action=bindings[key]
    if (!action || !actions[action] || (event.shiftKey && key.startsWith('arrow'))) return
    const target=event.composedPath()[0]
    if (target instanceof Element && target.closest('input,textarea,select,[contenteditable]:not([contenteditable="false"]),[role="textbox"],[role="menu"],[role="listbox"]')) return
    if (document.querySelector('dialog[open]:not(.fullscreen-reader),[role="dialog"][aria-modal="true"]:not(.fullscreen-reader)') || options.blocked?.()) return
    event.preventDefault()
    try { const result=actions[action]!(); if (result instanceof Promise) void result.catch(reason=>options.error?.(reason)); try { options.feedback?.(action) } catch { /* Feedback must not affect the action. */ } }
    catch (reason) { options.error?.(reason) }
  }
  document.addEventListener('keydown',keydown)
  return () => document.removeEventListener('keydown',keydown)
}
