<script setup>
import { reactive, ref } from 'vue'
import { api } from '../api/client'
import { copyText } from '../lib/copy'
import { loadSettings } from '../stores/settings'

// 이음단에 보낼 장소·일정 요청 메시지 (오프라인 멘토링). 멘티 이름은 넣지 않는다.
const f = reactive({ kind: '장소 요청', region: '', schedule: '', current: '', desired: '', reason: '' })
const res = ref(null)
const error = ref('')
const copied = ref(false)
const chatUrl = loadSettings().ieumdanChatUrl

async function build() {
  error.value = ''
  copied.value = false
  try {
    res.value = await api.ieumdanRequest({
      kind: f.kind, region: f.region, schedule: f.schedule, reason: f.reason,
      current: f.current || null, desired: f.desired || null,
    })
  } catch (e) {
    error.value = e.message
  }
}

async function copy() {
  copied.value = await copyText(res.value.message)
}
</script>

<template>
  <div class="shell">
    <h1>이음단 요청</h1>
    <form class="card" @submit.prevent="build">
      <label class="field"><span class="name">요청 종류</span>
        <select v-model="f.kind"><option>장소 요청</option><option>일정 변경</option><option>장소 변경</option></select>
      </label>
      <label v-if="f.kind !== '일정 변경'" class="field"><span class="name">희망 지역</span>
        <input v-model="f.region" placeholder="예: ○○구 ○○동 근처" maxlength="100" />
        <span class="notice">멘티의 이름, 학교, 집 주소는 쓰지 마세요.</span>
      </label>
      <label v-if="f.kind === '장소 요청'" class="field"><span class="name">희망 요일과 시간</span>
        <input v-model="f.schedule" placeholder="예: 매주 수 19:00~20:00" maxlength="100" />
      </label>
      <label v-if="f.kind !== '장소 요청'" class="field"><span class="name">{{ f.kind === '일정 변경' ? '지금 예약된 일시' : '언제부터 바꿀지 (예약된 일시)' }}</span>
        <input v-model="f.current" type="datetime-local" />
      </label>
      <label v-if="f.kind === '일정 변경'" class="field"><span class="name">바꾸고 싶은 일시</span><input v-model="f.desired" type="datetime-local" /></label>
      <label v-if="f.kind !== '장소 요청'" class="field"><span class="name">사유 (선택)</span><input v-model="f.reason" maxlength="200" /></label>
      <button class="primary">요청 메시지 만들기</button>
    </form>
    <div v-if="error" class="box error">{{ error }}</div>
    <template v-if="res">
      <div v-if="res.warnings.length" class="box warn" data-test="warnings"><ul><li v-for="w in res.warnings" :key="w">{{ w }}</li></ul></div>
      <div class="card">
        <div style="white-space: pre-wrap" data-test="message">{{ res.message }}</div>
        <div class="row" style="margin-top: 8px">
          <button type="button" @click="copy">메시지 복사</button>
          <a v-if="chatUrl" :href="chatUrl" target="_blank" rel="noopener noreferrer"><button type="button" class="primary">이음단 오픈채팅 열기</button></a>
          <span v-if="copied" class="ok">복사했습니다</span>
        </div>
        <p v-if="res.pii_masked.length" class="notice">가린 정보: {{ res.pii_masked.join(', ') }}</p>
      </div>
      <div class="card"><ul><li v-for="r in res.reminders" :key="r">{{ r }}</li></ul></div>
    </template>
  </div>
</template>
