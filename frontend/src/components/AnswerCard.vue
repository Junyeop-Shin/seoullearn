<script setup>
import { copyText } from '../lib/copy'

// 답변 한 건: 본문, 근거 카드, 문의처 카드, 문의 초안, 가린 개인정보.
const props = defineProps({ res: { type: Object, required: true } })
// 보고서와 계획서는 멘티를 고른 뒤 그 멘티 화면에서 쓴다
const SCREEN = { report: '/mentees', plan: '/mentees', calc: '/allowance' }
const LABEL = { report: '내 멘티에서 활동보고서 쓰기', plan: '내 멘티에서 종합계획서 쓰기' }

const copyDraft = () => copyText(props.res.inquiry_draft, '문의 초안')
</script>

<template>
  <div class="bubble bot">
    <div>{{ res.answer }}</div>
    <div v-if="res.screen" class="row gap-top">
      <router-link :to="SCREEN[res.intent] || '/'" class="linkbutton primary small">{{ LABEL[res.intent] || `${res.screen} 화면으로 이동` }}</router-link>
    </div>
    <ul v-if="res.required_inputs?.length" class="muted"><li v-for="x in res.required_inputs" :key="x">{{ x }}</li></ul>

    <div v-if="res.citations?.length" class="cards" data-test="citations">
      <div v-for="c in res.citations" :key="c" class="mini"><span class="t">근거</span>{{ c }}</div>
    </div>
    <div v-if="res.route" class="cards" data-test="route">
      <div class="mini">
        <span class="t">문의처: {{ res.route }}</span>
        <span>{{ res.route_info }}</span>
        <div v-if="res.route === '이음단'" class="gap-top">
          <router-link to="/ieumdan" class="linkbutton small primary" data-test="route-contacts">자치구별 이음단 카카오톡 채널 보기</router-link>
        </div>
      </div>
    </div>
    <div v-if="res.inquiry_draft" class="mini gap-top" data-test="inquiry">
      <span class="t">문의 초안</span>
      <div class="pre">{{ res.inquiry_draft }}</div>
      <div class="row gap-top">
        <button type="button" class="small" @click="copyDraft">문의 초안 복사</button>
        <span class="muted">{{ res.inquiry_contact }}</span>
      </div>
    </div>
    <p v-if="res.pii_masked?.length" class="notice" data-test="pii">AI에 보내기 전에 가린 정보: {{ res.pii_masked.join(', ') }}</p>
  </div>
</template>
