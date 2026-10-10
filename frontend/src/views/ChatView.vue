<script setup>
import { nextTick, ref } from 'vue'
import { api } from '../api/client'
import AnswerCard from '../components/AnswerCard.vue'

const messages = ref([])
const text = ref('')
const busy = ref(false)
const error = ref('')
const bottom = ref(null)
const EXAMPLES = ['멘티가 20분 늦게 왔는데 어떻게 처리하나요?', '활동보고서는 언제까지 내야 해요?', '오프라인 장소는 어떻게 잡아요?', '온라인 멘토링은 시간당 얼마 받아요?']

function ask(q) {
  text.value = q
  send()
}

async function send() {
  const q = text.value.trim()
  if (q.length < 2 || busy.value) return
  error.value = ''
  messages.value.push({ me: true, text: q })
  text.value = ''
  busy.value = true
  try {
    const res = await api.chat(q)
    messages.value.push({ me: false, res })
  } catch (e) {
    error.value = e.message
    messages.value.pop()   // 보내지 못한 질문은 입력창으로 되돌린다
    text.value = q
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
    <div v-if="!messages.length" class="card" data-test="empty">
      <strong>이렇게 물어보세요</strong>
      <div class="chips">
        <button v-for="q in EXAMPLES" :key="q" type="button" class="chip" @click="ask(q)">{{ q }}</button>
      </div>
      <p class="notice">"활동보고서 쓰고 싶어"처럼 적으면 쓰는 화면으로 안내해 드립니다. Enter로 보내고, Shift+Enter로 줄을 바꿉니다.</p>
    </div>
    <div class="chat">
      <template v-for="(m, i) in messages" :key="i">
        <div v-if="m.me" class="bubble me">{{ m.text }}</div>
        <AnswerCard v-else :res="m.res" />
      </template>
      <div v-if="busy" class="bubble bot muted" aria-live="polite">답변을 찾는 중입니다… <span class="dots"><span></span><span></span><span></span></span></div>
      <div ref="bottom"></div>
    </div>
    <div v-if="error" class="box error">{{ error }}</div>
    <div class="composer">
      <form class="card" @submit.prevent="send">
        <textarea v-model="text" placeholder="예: 멘티가 20분 늦게 왔는데 어떻게 처리하나요?" maxlength="1000" aria-label="질문 입력"
          @keydown.enter.exact="(e) => e.isComposing || (e.preventDefault(), send())"></textarea>
        <div class="row gap-top">
          <span class="notice grow">멘티 이름·연락처·학교는 쓰지 마세요. 적혀 있으면 AI에 보내기 전에 가립니다.</span>
          <button class="primary" :disabled="busy || text.trim().length < 2">질문하기</button>
        </div>
      </form>
    </div>
  </div>
</template>
