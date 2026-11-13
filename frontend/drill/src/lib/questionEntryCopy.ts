import { accountPreferences } from '../../../shared/preferences/store'
import { usePracticePreferences } from './practicePreferences'
import { fetchQuestion } from './workspace'
import { sourcePracticeTarget } from './sourcePractice'
import { withWorkspacePrefix } from './runtimePath'
import { copyImagesToClipboard } from './imageClipboard'
import { createAndCopyShareOnGesture } from './share'

type Result = { copied: boolean; message: string }
type Task = { uuid: string; canonical?: string; owner: string; result: Promise<Result> }
let pending: Task | null = null
const keys = ['type_group','exam_type','document','topic','source_category','q','unattempted','marker','collection','bucket','tier','kind','material','combined','state','scope','course','mode','sort','search_version','index_version','status','favorite','review_later','practice_page','insight_return','insight_list','collection_page','from']
export function armQuestionEntryCopy(uuid: string, query: Record<string, unknown>) {
 const prefs = usePracticePreferences(), mode = prefs.pageTurnCopyMode.value, owner = accountPreferences.userId.value
 if (!owner || mode === 'off') return null
 const params = query.from === 'preview' ? '' : new URLSearchParams(Object.fromEntries(keys.filter(key => query[key] !== undefined && query[key] !== '').map(key => [key,String(query[key])]))).toString()
 const task = { uuid, owner, result: Promise.resolve({copied:false,message:''}) } as Task
 const current = () => accountPreferences.userId.value === owner
 const loaded = fetchQuestion(uuid, params, true).then(async value => {
  if (!current()) throw new Error('账号已变化，已取消复制。')
  const canonical = sourcePracticeTarget(value, query.view)
  task.canonical = canonical || uuid
  return canonical ? fetchQuestion(canonical, params, true) : value
 })
 // These APIs start synchronously in the router's originating click/keypress;
 // their ClipboardItem holds a promise while authenticated content is loaded.
 if (mode === 'image') {
  const urls = loaded.then(value => {
   if (!current()) throw new Error('账号已变化，已取消复制。')
   return (value.question_assets || value.assets || []).map(asset => withWorkspacePrefix(asset.url))
  })
  void urls.catch(() => {})
  task.result = copyImagesToClipboard(urls, prefs.imageCopyScale.value).then(result => ({copied:true,message:result.limited ? '当前题题图已自动复制（已限制输出尺寸）✓' : '当前题题图已自动复制 ✓'}))
 } else {
  const endpoint = loaded.then(value => {
   if (!current()) throw new Error('账号已变化，已取消复制。')
   return `/api/drill/questions/${value.uuid}/share/`
  })
  task.result = createAndCopyShareOnGesture(endpoint).then(({copied}) => ({copied,message:copied ? '当前题分享链接已自动复制 ✓' : '浏览器阻止了自动复制，请点击「复制分享链接」重试。'}))
 }
 task.result = task.result.catch(() => ({copied:false,message:'浏览器未允许自动复制，请点击「复制题图」或「复制分享链接」重试。'}))
 pending = task
 return task
}
export function takeQuestionEntryCopy(uuid: string) {
 if (pending?.owner !== accountPreferences.userId.value || (pending.uuid !== uuid && pending.canonical !== uuid)) return null
 const task = pending; pending = null; return task
}
