import { applyVisualPreferences, cookieValue, localValue, readVisualPreferences } from './resolve'
applyVisualPreferences(readVisualPreferences())
const language = cookieValue('learning_os_ui_language') || localValue('learning-os-ui-language')
if (language && ['en', 'zh-CN', 'ja'].includes(language)) document.documentElement.lang = language
