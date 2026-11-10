<script setup lang="ts">
import { uiText } from '../lib/uiText'
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const router = useRouter()
const route = useRoute()
const requestedPath = computed(() => route.fullPath)
const retry = () => window.location.reload()
const goBack = () => {
  const referrer = document.referrer
  if (window.history.length > 1 && referrer.startsWith(window.location.origin)) router.back()
  else void router.push('/practice')
}
</script>

<template>
  <section class="page route-error-page" role="alert">
    <span class="eyebrow">{{ uiText("页面未找到 · 404") }}</span>
    <h1>{{ uiText("这个地址无法识别") }}</h1>
    <p>{{ uiText("链接可能输入错误、已经失效，或者页面已被移动。题库和学习记录没有因此发生变化。") }}</p>
    <code>{{ requestedPath }}</code>
    <div>
      <button type="button" @click="retry">{{ uiText("重试") }}</button>
      <RouterLink to="/practice">{{ uiText("返回题库") }}</RouterLink>
      <button type="button" @click="goBack">{{ uiText("返回上一页") }}</button>
    </div>
  </section>
</template>
