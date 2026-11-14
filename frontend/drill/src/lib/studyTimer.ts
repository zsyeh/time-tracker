import { api } from './api'

export type StudyWorkspace = 'drill' | 'ei'
export type StudySession = { id: number; subject: string }
export const studySubject = (workspace: StudyWorkspace) => workspace === 'drill' ? 'math' : 'major'

async function request<T>(url: string, options: RequestInit = {}, timeout = 4000) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeout)
  try { return await api<T>(url, { ...options, signal: controller.signal }) }
  finally { clearTimeout(timer) }
}

export async function activeStudyTimer(): Promise<StudySession | null> {
  const page = await request<{ results: StudySession[] }>('/api/sessions/?status=running')
  return page.results[0] || null
}

export async function startStudyTimer(workspace: StudyWorkspace) {
  const result = await request<{ session: StudySession }>('/api/sessions/', {
    method: 'POST', body: JSON.stringify({
      subject: studySubject(workspace), topic: workspace === 'drill' ? 'Drill' : 'EI', learning_mode: 'exercise',
    }),
  }, 8000)
  if (result.session.subject !== studySubject(workspace)) throw new Error('Unexpected study timer subject')
  return result.session
}
