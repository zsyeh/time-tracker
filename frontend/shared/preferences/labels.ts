export const navigationLabels:Record<string,[string,string]>={
 today:['Today','今日'],trends:['Trends','学习趋势'],sessions:['Sessions','学习记录'],issues:['Issues','问题'],
 'subject-math':['Mathematics','数学'],'subject-english':['English','英语'],'subject-major':['Major / 892','专业课 / 892'],'subject-training':['Politics','政治'],
 'selected-heatmap':['Selected heatmap','严选题热力图'],'core-heatmap':['Core heatmap','五科核心热力图'],insight:['History','历史记录'],progress:['Learning progress','学习进度'],cockpit:['892 overview','892 总览'],practice:['Question bank','Practice 题库'],diagnostics:['Problem-solving analysis','解题能力'],
 'circuit-selected':['Circuit selected','电路严选'],'signal-selected':['Signal selected','信号严选'],'signal-formulas':['Daily formulas','每日公式'],'analog-selected':['Analog selected','模电严选'],'digital-selected':['Digital selected','数电严选'],'communication-selected':['Communication selected','通信严选'],'selected-pdf-pages':['Selected PDF pages','严选 PDF 页码'],
 activity:['Activity','活跃记录'],'book-activity':['Book activity','书目打卡'],heatmap:['Knowledge map','知识热力图'],papers:['Papers','组卷'],favorites:['Favorites','收藏'],'review-later':['Review later','下次复习'],feel:['Book reflections','书目感受'],errata:['Errata','勘误'],
}
export function navigationLabel(id:string,language:string){return navigationLabels[id]?.[language==='en'?0:1] || id}
