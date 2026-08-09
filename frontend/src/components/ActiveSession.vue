<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { post } from '../lib/api'
import type { StudySession, Subject } from '../types'

const props = defineProps<{ session: StudySession | null }>()
const emit = defineEmits<{ changed: [] }>()
const finishOpen = ref(false)
const saving = ref(false)
const now = ref(Date.now())
let ticker = 0
const form = reactive({
  chapter: '', topic: '', learning_mode: 'theory', difficulty: 3, energy_level: 'medium',
  focus_level: 3, confidence_after: 3, note: '', breakthrough: '', problems: '', next_action: '',
})
const subjects: Array<{ id: Subject; label: string; shortcut: string }> = [
  { id: 'math', label: '数学', shortcut: 'M' }, { id: 'english', label: '英语', shortcut: 'E' },
  { id: 'major', label: '专业课', shortcut: 'P' }, { id: 'training', label: '训练', shortcut: 'T' },
]
const elapsed = computed(() => {
  if (!props.session) return '00:00:00'
  const seconds = Math.max(0, Math.floor((now.value - new Date(props.session.start_time).getTime()) / 1000))
  const h = Math.floor(seconds / 3600).toString().padStart(2, '0')
  const m = Math.floor(seconds % 3600 / 60).toString().padStart(2, '0')
  const s = (seconds % 60).toString().padStart(2, '0')
  return `${h}:${m}:${s}`
})

onMounted(() => { ticker = window.setInterval(() => { now.value = Date.now() }, 1000) })
onBeforeUnmount(() => window.clearInterval(ticker))

async function start(subject: Subject) {
  try {
    await post('/api/sessions/', { subject })
    ElMessage.success('学习计时已开始')
    emit('changed')
  } catch (error) { ElMessage.error((error as Error).message) }
}

function prepareFinish() {
  if (!props.session) return
  form.chapter = props.session.chapter
  form.topic = props.session.topic
  form.learning_mode = props.session.learning_mode || 'theory'
  finishOpen.value = true
}

async function finish() {
  if (!props.session) return
  if (!(form.chapter.trim() || form.topic.trim()) || !form.note.trim() || !form.breakthrough.trim() || !form.problems.trim() || !form.next_action.trim()) {
    ElMessage.warning('请完整填写主题/章节、总结、突破、问题和下一步')
    return
  }
  saving.value = true
  try {
    await post(`/api/sessions/${props.session.id}/finish/`, form)
    finishOpen.value = false
    ElMessage.success('学习记录已完成')
    emit('changed')
  } catch (error) { ElMessage.error((error as Error).message) } finally { saving.value = false }
}

async function abandon() {
  if (!props.session) return
  try {
    await ElMessageBox.confirm('这次计时会标记为已放弃，不计入学习统计。', '放弃本次学习？', { type: 'warning' })
    await post(`/api/sessions/${props.session.id}/abandon/`)
    emit('changed')
  } catch (error) { if (error !== 'cancel') ElMessage.error((error as Error).message) }
}
</script>

<template>
  <section class="focus-panel" :class="{ active: session }">
    <template v-if="session">
      <div><span class="pulse-dot" /><span class="eyebrow">SESSION IN PROGRESS</span><h2>{{ session.subject_label }}学习中</h2><p>{{ session.topic || session.chapter || '专注当下，结束时再认真复盘。' }}</p></div>
      <div class="active-clock">{{ elapsed }}</div>
      <div class="active-actions"><el-button plain @click="abandon">放弃</el-button><el-button type="primary" @click="prepareFinish">完成并复盘</el-button></div>
    </template>
    <template v-else>
      <div><span class="eyebrow">QUICK START</span><h2>准备好开始了吗？</h2><p>服务器记录准确开始时间；重复点击同一科目不会产生重复记录。</p></div>
      <div class="subject-actions">
        <button v-for="item in subjects" :key="item.id" :class="`subject-button subject-${item.id}`" @click="start(item.id)"><b>{{ item.shortcut }}</b><span>{{ item.label }}</span></button>
      </div>
    </template>
  </section>

  <el-dialog v-model="finishOpen" title="完成学习 · 结构化复盘" width="min(720px, 94vw)" destroy-on-close>
    <el-form label-position="top" class="review-form">
      <div class="form-pair"><el-form-item label="章节"><el-input v-model="form.chapter" placeholder="例如：第三章" /></el-form-item><el-form-item label="学习主题"><el-input v-model="form.topic" placeholder="今天具体学了什么" /></el-form-item></div>
      <div class="form-pair"><el-form-item label="学习模式"><el-select v-model="form.learning_mode"><el-option v-for="item in [['theory','理论'],['exercise','练习'],['review','复习'],['memorization','记忆'],['project','项目'],['exam_simulation','模考']]" :key="item[0]" :label="item[1]" :value="item[0]" /></el-select></el-form-item><el-form-item label="专注度"><el-rate v-model="form.focus_level" /></el-form-item></div>
      <el-form-item label="学习总结（必填）"><el-input v-model="form.note" type="textarea" :rows="3" placeholder="记录事实、方法和结果" /></el-form-item>
      <el-form-item label="今天的突破（必填）"><el-input v-model="form.breakthrough" type="textarea" :rows="2" /></el-form-item>
      <el-form-item label="仍然存在的问题（必填）"><el-input v-model="form.problems" type="textarea" :rows="2" /></el-form-item>
      <el-form-item label="下一步行动（必填）"><el-input v-model="form.next_action" type="textarea" :rows="2" /></el-form-item>
    </el-form>
    <template #footer><el-button @click="finishOpen = false">暂不结束</el-button><el-button type="primary" :loading="saving" @click="finish">保存并完成</el-button></template>
  </el-dialog>
</template>
