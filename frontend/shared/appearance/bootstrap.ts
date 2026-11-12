import { readPreferenceBootstrap } from '../preferences/bootstrap'
import { fontScales } from '../preferences/schema'
import { applyVisualPreferences, cookieValue, localValue, readVisualPreferences } from './resolve'
applyVisualPreferences(readVisualPreferences())
const language = cookieValue('learning_os_ui_language') || localValue('learning-os-ui-language')
if (language && ['en', 'zh-CN', 'ja'].includes(language)) document.documentElement.lang = language

const account=readPreferenceBootstrap()
if(account){document.documentElement.style.setProperty('--ui-font-scale',String(fontScales[account.snapshot?.values.font || 'small']));document.documentElement.dataset.fontSize=account.snapshot?.values.font || 'small';document.documentElement.lang=account.snapshot?.values.language || 'en'}
