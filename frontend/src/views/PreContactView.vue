<script setup>
import { ref } from 'vue'
import { api } from '../api/client'
import { copyText } from '../lib/copy'

// 사전 연락: 매칭 직후 보낼 문자 초안. 통화에서 들은 내용은 '내 멘티'에 적어 두면 종합계획서에 쓰인다.
const mode = ref('온라인')
const callTime = ref('')
const res = ref(null)
const error = ref('')

async function build() {
  error.value = ''
  try {
    res.value = await api.preContact(mode.value, callTime.value)
  } catch (e) {
    error.value = e.message
  }
}
</script>

<template>
  <div class="shell">
    <h1>사전 연락</h1>
    <p class="muted">매칭 직후 멘티(보호자)에게 보낼 문자 초안을 만듭니다.</p>
    <form class="card" @submit.prevent="build">
      <div class="form-grid">
        <label class="field"><span class="name">멘토링 유형</span>
          <select v-model="mode"><option>온라인</option><option>오프라인</option></select>
        </label>
        <label class="field"><span class="name">전화할 시각 (선택)</span><input v-model="callTime" placeholder="예: 19시" maxlength="20" /></label>
      </div>
      <button class="primary">문자 초안 만들기</button>
    </form>
    <div v-if="error" class="box error">{{ error }}</div>
    <template v-if="res">
      <h2>문자 초안 <span class="tag">{{ res.sms.length }}자</span></h2>
      <div class="card">
        <p class="muted">[멘토명], [멘티명]은 보내기 전에 직접 채워 주세요.</p>
        <div class="mini" style="white-space: pre-wrap" data-test="sms">{{ res.sms.text }}</div>
        <div class="row" style="margin-top: 10px"><button type="button" class="primary" @click="copyText(res.sms.text)">문자 복사</button></div>
      </div>
      <div class="box warn"><ul><li v-for="n in res.notes" :key="n">{{ n }}</li></ul></div>
      <p class="muted">통화에서 들은 과목, 일정, 목표는 <router-link to="/mentees">내 멘티</router-link>에 적어 두면 종합계획서와 활동보고서에 자동으로 채워집니다.</p>
    </template>
  </div>
</template>
