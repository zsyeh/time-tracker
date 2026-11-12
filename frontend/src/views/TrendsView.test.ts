// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import TrendsView from './TrendsView.vue'
import type { Overview } from '../types'
const chart = vi.hoisted(() => ({ init: vi.fn(), setOption: vi.fn(), resize: vi.fn(), dispose: vi.fn() }))
vi.mock('../lib/charts', () => ({ init: chart.init }))
vi.mock('../components/layout/PageHeader.vue', () => ({ default: { template: '<header><slot name="actions" /></header>' } }))
let app: App | undefined
let host: HTMLDivElement
const data = { range_days: 60, calendar: { today: '2026-11-12' }, heatmap: [{ date: '2026-11-11', minutes: 180, first_start: '08:30', is_future: false }, { date: '2026-11-12', minutes: 300, first_start: '09:00', is_future: false }, { date: '2026-12-19', minutes: 0, first_start: null, is_future: true }], subject_totals: [], summary: { total_minutes: 480, average_start_time: '08:45', five_hour_days: 1, current_five_hour_streak: 1, session_count: 2 }, weekly_totals: [], monthly_totals: [], tag_totals: [], task_totals: [] } as unknown as Overview
beforeEach(() => { vi.clearAllMocks(); chart.init.mockReturnValue(chart); host = document.createElement('div'); document.body.append(host); vi.stubGlobal('ResizeObserver', class { observe = vi.fn(); disconnect = vi.fn() }); vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => window.setTimeout(() => callback(0), 0)); vi.stubGlobal('cancelAnimationFrame', (id: number) => clearTimeout(id)) })
afterEach(() => { app?.unmount(); app = undefined; host.remove(); vi.unstubAllGlobals() })
async function settle() { await nextTick(); await Promise.resolve(); await nextTick(); await new Promise(resolve => setTimeout(resolve, 10)) }
it('keeps historical data and redraws on appearance/rotation without replacing the statistics', async () => {
 app = createApp(TrendsView, { overview: data }); app.mount(host); await settle()
 const option = chart.setOption.mock.calls.at(-1)?.[0]
 expect(option.series[0].data).toContain(180)
 expect(option.xAxis.data).not.toContain('12-19')
 expect(option.xAxis.axisLabel.fontSize).toBe(12)
 expect(option.tooltip.textStyle.fontSize).toBe(14)
 const calls = chart.setOption.mock.calls.length
 window.dispatchEvent(new Event('learning:appearance-changed')); await settle()
 expect(chart.setOption.mock.calls.length).toBeGreaterThan(calls)
 expect(chart.setOption.mock.calls.at(-1)?.[0].series[0].data).toEqual(option.series[0].data)
 window.dispatchEvent(new Event('orientationchange')); await settle(); expect(chart.resize).toHaveBeenCalled()
 expect(host.querySelector('.chart-data tbody')?.textContent).toContain('2026-11-11')
 expect(host.querySelector('.chart-data tbody')?.textContent).not.toContain('2026-12-19')
 app.unmount(); app = undefined; expect(chart.dispose).toHaveBeenCalled()
 const renders = chart.setOption.mock.calls.length
 window.dispatchEvent(new Event('learning:appearance-changed')); await settle(); expect(chart.setOption).toHaveBeenCalledTimes(renders)
})
