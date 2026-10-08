<script setup>
import { nextTick, ref } from 'vue'
import { api } from '../api/client'
import AnswerCard from '../components/AnswerCard.vue'
import { loadSettings } from '../stores/settings'

const messages = ref([])
const text = ref('')
const busy = ref(false)
const error = ref('')
const bottom = ref(null)

async function send() {
  const q = text.value.trim()
  if (q.length < 2 || busy.value) return
  error.value = ''
  messages.value.push({ me: true, text: q })
  text.value = ''
  busy.value = true
  try {
    const res = await api.chat(q, loadSettings().ieumdanChatUrl)
    messages.value.push({ me: false, res })
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
    await nextTick()
    bottom.value?.scrollIntoView({ behavior: 'smooth' })
  }
}
</script>

<template>
  <div class="shell">
    <h1>매뉴얼 질문</h1>
    <p class="muted">활동가이드와 공지에서 답을 찾아 근거와 함께 알려 드립니다. 답이 없으면 문의처와 문의 초안을 드립니다.</p>
    <div class="chat">
      <template v-for="(m, i) in messages" :key="i">
        <div v-if="m.me" class="bubble me">{{ m.text }}</div>
        <AnswerCard v-else :res="m.res" />
      </template>
      <div v-if="busy" class="bubble bot muted">답변을 찾는 중입니다…</div>
      <div ref="bottom"></div>
    </div>
    <div v-if="error" class="box error">{{ error }}</div>
    <form class="card" @submit.prevent="send">
      <textarea v-model="text" placeholder="예: 멘티가 20분 늦게 왔는데 어떻게 처리하나요?" maxlength="1000"
        @keydown.enter.exact.prevent="send"></textarea>
      <div class="row" style="margin-top: 8px">
        <button class="primary" :disabled="busy || text.trim().length < 2">질문하기</button>
        <span class="notice">멘티 이름·연락처·학교는 쓰지 마세요. 적혀 있으면 AI에 보내기 전에 가립니다.</span>
      </div>
    </form>
  </div>
</template>
