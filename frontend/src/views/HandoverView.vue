<script setup>
import { useRoute } from 'vue-router'
import MenteeHeader from '../components/MenteeHeader.vue'
import { reactive, ref } from 'vue'
import { api } from '../api/client'
import ReportSource from '../components/ReportSource.vue'
import { copyText } from '../lib/copy'
import { saveItem } from '../stores/vault'

// 멘토 교체 인계 요약: 출석 패턴, 과제 수행, 학습 태도, 수강 강의·진도만 넘긴다.
const alias = ref(String(useRoute().params.alias))
const reports = ref([])
const res = ref(null)
const summary = reactive({})
const busy = ref(false)
const error = ref('')
const status = ref('')

async function build() {
  error.value = status.value = ''
  busy.value = true
  try {
    res.value = await api.handover(reports.value)
    for (const k of Object.keys(summary)) delete summary[k]
    Object.assign(summary, res.value.summary)
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

function asText() {
  return Object.entries(summary).filter(([, v]) => v.trim()).map(([k, v]) => `[${res.value.labels[k]}] ${v}`).join('\n')
}

async function copyAll() {
  status.value = (await copyText(asText())) ? '복사했습니다.' : '복사하지 못했습니다.'
}

async function save() {
  try {
    await saveItem({ alias: alias.value, formId: 'handover_summary', title: '인계 요약', draft: { ...summary } })
    status.value = '보관함에 저장했습니다.'
  } catch (e) {
    status.value = e.message
  }
}
</script>

<template>
  <div class="shell">
    <MenteeHeader :alias="alias" title="인계 요약" />
    <h1>인계 요약</h1>
    <p class="muted">멘토가 바뀔 때 다음 멘토에게 넘길 내용입니다. 아래 네 가지만 만들고, 성적·이해도 같은 학업 수준과 정서·상담 내용은 넣지 않습니다.</p>
    <div v-if="error" class="box error">{{ error }}</div>
    <ReportSource :alias="alias" @loaded="reports = $event.reports" />
    <button type="button" class="primary" :disabled="busy || !reports.length" @click="build">{{ busy ? '요약을 만드는 중입니다…' : '인계 요약 만들기' }}</button>
    <template v-if="res">
      <div v-if="res.warnings.length" class="box warn" data-test="warnings"><ul><li v-for="w in res.warnings" :key="w">{{ w }}</li></ul></div>
      <p v-if="res.pii_masked.length" class="notice">AI에 보내기 전에 가린 정보: {{ res.pii_masked.join(', ') }}</p>
      <label v-for="(label, k) in res.labels" :key="k" class="field">
        <span class="name">{{ label }}</span>
        <textarea v-model="summary[k]" :data-summary="k"></textarea>
      </label>
      <div class="row">
        <button type="button" @click="copyAll">전체 복사</button>
        <button type="button" @click="save">보관함에 저장</button>
        <span>{{ status }}</span>
      </div>
      <div class="card"><ul><li v-for="r in res.reminders" :key="r">{{ r }}</li></ul></div>
    </template>
  </div>
</template>
