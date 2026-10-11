<script setup>
import { nextTick, ref } from 'vue'
import { api } from '../api/client'
import AnswerCard from '../components/AnswerCard.vue'
import { busy, clearChat, error, messages } from '../stores/chat'

const text = ref('')
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
  const list = messages.value   // 로그아웃하거나 대화를 지우면 새 배열로 바뀐다: 그 뒤에 온 답은 버린다 (다음 사용자에게 보이지 않게)
  const mine = { me: true, text: q }
  list.push(mine)
  text.value = ''
  busy.value = true
  try {
    const res = await api.chat(q)
    if (messages.value === list) list.push({ me: false, res })
  } catch (e) {
    if (messages.value !== list) return
    error.value = e.message
    list.splice(list.indexOf(mine), 1)   // 보내지 못한 질문은 입력창으로 되돌린다
    text.value = q
  } finally {
    if (messages.value === list) busy.value = false
    await nextTick()
    bottom.value?.scrollIntoView()
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
      <p class="notice">앞의 질문은 기억하지 않습니다. 질문 하나에 필요한 내용을 모두 적어 주세요. Enter로 보내고 Shift+Enter로 줄을 바꿉니다.</p>
    </div>
    <div v-else class="row"><span class="grow"></span><button type="button" class="small" data-test="clear-chat" @click="clearChat">대화 지우기</button></div>
    <div class="chat" aria-live="polite">
      <template v-for="(m, i) in messages" :key="i">
        <div v-if="m.me" class="bubble me">{{ m.text }}</div>
        <AnswerCard v-else :res="m.res" />
      </template>
      <div v-if="busy" class="bubble bot muted">답변을 찾는 중입니다… <span class="dots"><span></span><span></span><span></span></span></div>
      <div ref="bottom"></div>
    </div>
    <div v-if="error" class="box error" role="alert">{{ error }}</div>
    <div class="composer">
      <form class="card" @submit.prevent="send">
        <textarea v-model="text" placeholder="예: 멘티가 20분 늦게 왔는데 어떻게 처리하나요?" maxlength="1000" aria-label="질문 입력"
          @keydown.enter.exact="(e) => e.isComposing || (e.preventDefault(), send())"></textarea>
        <div class="row gap-top">
          <span class="notice grow">멘티 이름·연락처·학교는 쓰지 마세요. 적혀 있으면 AI로 보내기 전에 가립니다.</span>
          <button class="primary" :disabled="busy || text.trim().length < 2">질문하기</button>
        </div>
      </form>
    </div>
  </div>
</template>
