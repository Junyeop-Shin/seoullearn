<script setup>
import { ref } from 'vue'
import { copyText } from '../lib/copy'

// 답변 한 건: 본문, 근거 카드, 문의처 카드, 문의 초안, 가린 개인정보.
const props = defineProps({ res: { type: Object, required: true } })
const copied = ref(false)
const SCREEN = { report: '/report', plan: '/plan', calc: '/allowance' }

async function copyDraft() {
  copied.value = await copyText(props.res.inquiry_draft)
}
</script>

<template>
  <div class="bubble bot">
    <div>{{ res.answer }}</div>
    <div v-if="res.screen" class="row" style="margin-top: 8px">
      <router-link :to="SCREEN[res.intent] || '/'"><button type="button" class="primary small">{{ res.screen }} 화면으로 이동</button></router-link>
    </div>
    <ul v-if="res.required_inputs?.length" class="muted"><li v-for="x in res.required_inputs" :key="x">{{ x }}</li></ul>

    <div v-if="res.citations?.length" class="cards" data-test="citations">
      <div v-for="c in res.citations" :key="c" class="mini"><span class="t">근거</span>{{ c }}</div>
    </div>
    <div v-if="res.route" class="cards" data-test="route">
      <div class="mini">
        <span class="t">문의처: {{ res.route }}</span>
        <span>{{ res.route_info }}</span>
        <div v-if="res.route_link" style="margin-top: 6px">
          <a :href="res.route_link" target="_blank" rel="noopener noreferrer"><button type="button" class="small primary">이음단 오픈채팅 열기</button></a>
        </div>
        <div v-else-if="res.route === '이음단'" class="notice">설정에서 소속 이음단 오픈채팅 주소를 저장하면 여기에 바로가기 버튼이 나옵니다.</div>
      </div>
    </div>
    <div v-if="res.inquiry_draft" class="mini" style="margin-top: 8px" data-test="inquiry">
      <span class="t">문의 초안</span>
      <div style="white-space: pre-wrap">{{ res.inquiry_draft }}</div>
      <div class="row" style="margin-top: 6px">
        <button type="button" class="small" @click="copyDraft">문의 초안 복사</button>
        <span v-if="copied" class="ok">복사했습니다</span>
        <span class="muted">{{ res.inquiry_contact }}</span>
      </div>
    </div>
    <p v-if="res.pii_masked?.length" class="notice" data-test="pii">AI에 보내기 전에 가린 정보: {{ res.pii_masked.join(', ') }}</p>
  </div>
</template>
