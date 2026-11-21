/** iPad's keyboard pans the visual viewport even when the layout body is locked.
 * Keep only the existing landscape split workspace inside that visible rectangle.
 * No window.scrollTo, focus changes, key interception, or changes to phone scrolling.
 */
export function installPracticeKeyboardViewport(): () => void {
  const viewport = window.visualViewport
  const appleTouch = /iPad|iPhone|iPod/.test(navigator.userAgent)
    || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1)
  if (!viewport || !appleTouch) return () => {}
  const split = window.matchMedia('(min-width: 1000px) and (min-height: 500px) and (orientation: landscape)')
  let frame = 0
  let shell: HTMLElement | null = null
  const clear = () => {
    shell?.classList.remove('practice-keyboard-viewport')
    shell?.style.removeProperty('--practice-visible-height')
    shell?.style.removeProperty('--practice-visible-top')
  }
  const update = () => {
    frame = 0
    shell = document.querySelector<HTMLElement>('.drill-shell.question-route')
    const editor = document.activeElement
    const editing = editor instanceof HTMLElement && shell?.contains(editor)
      && editor.matches('textarea, input:not([type=checkbox]):not([type=radio]), [contenteditable=true]')
    const shifted = window.innerHeight - viewport.height > 100 || viewport.offsetTop > 1
    if (!shell || !split.matches || Math.abs(viewport.scale - 1) > 0.01 || !shifted
      || (!editing && !shell.classList.contains('practice-keyboard-viewport'))) {
      clear()
      return
    }
    shell.style.setProperty('--practice-visible-height', `${viewport.height}px`)
    shell.style.setProperty('--practice-visible-top', `${viewport.offsetTop}px`)
    shell.classList.add('practice-keyboard-viewport')
    // Reveal the editor using its own column, never Safari's document scroller.
    if (editing && editor instanceof HTMLElement) {
      const pane = editor.closest<HTMLElement>('.question-control-pane')
      if (pane) {
        const field = editor.getBoundingClientRect(), bounds = pane.getBoundingClientRect()
        const bottom = Math.min(bounds.bottom, viewport.offsetTop + viewport.height) - 12
        const top = Math.max(bounds.top, viewport.offsetTop) + 12
        if (field.height > bottom - top) return
        if (field.bottom > bottom) pane.scrollTop += field.bottom - bottom
        else if (field.top < top) pane.scrollTop -= top - field.top
      }
    }
  }
  const schedule = () => { if (!frame) frame = requestAnimationFrame(update) }
  viewport.addEventListener('resize', schedule)
  viewport.addEventListener('scroll', schedule)
  window.addEventListener('resize', schedule)
  document.addEventListener('focusin', schedule)
  document.addEventListener('focusout', schedule)
  document.addEventListener('input', schedule)
  split.addEventListener('change', schedule)
  return () => {
    cancelAnimationFrame(frame)
    viewport.removeEventListener('resize', schedule)
    viewport.removeEventListener('scroll', schedule)
    window.removeEventListener('resize', schedule)
    document.removeEventListener('focusin', schedule)
    document.removeEventListener('focusout', schedule)
    document.removeEventListener('input', schedule)
    split.removeEventListener('change', schedule)
    clear()
  }
}
