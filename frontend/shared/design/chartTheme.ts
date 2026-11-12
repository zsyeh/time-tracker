function token(name: string, fallback: string, legacy?: string) {
  const root=document.querySelector('.drill-shell') || document.documentElement
  const styles=getComputedStyle(root)
  return styles.getPropertyValue(name).trim() || (legacy && styles.getPropertyValue(legacy).trim()) || fallback
}
export function chartPalette() {
  return {text:token('--text-secondary','#b0b0b0'),primary:token('--text-primary','#ededed'),border:token('--border-subtle','#2a2a2a'),surface:token('--surface-elevated','#242424','--bg-elevated'),accent:token('--accent-ink','#8ab4ff','--accent'),mastered:token('--status-success','#74c99a','--mastered'),review:token('--status-review','#dfbd6b','--review'),comparison:token('--text-secondary','#b0b0b0'),danger:token('--status-danger','#f19a9f')}
}
export function chartVisuals(palette:ReturnType<typeof chartPalette>) {
  const reduced=typeof matchMedia!=='undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches
  return {animationDuration:reduced?0:180,animationDurationUpdate:reduced?0:180,textStyle:{fontFamily:'-apple-system, BlinkMacSystemFont, Segoe UI, PingFang SC, sans-serif',fontSize:12},tooltip:{trigger:'axis' as const,confine:true,backgroundColor:palette.surface,borderColor:palette.border,textStyle:{color:palette.primary,fontSize:14}}}
}
export function onChartAppearanceChanged(render:()=>unknown) {
  let queued=false,stopped=false
  const update=()=>{if(queued||stopped)return;queued=true;queueMicrotask(()=>{queued=false;if(!stopped)render()})}
  window.addEventListener('learning:appearance-changed',update)
  return ()=>{stopped=true;window.removeEventListener('learning:appearance-changed',update)}
}
