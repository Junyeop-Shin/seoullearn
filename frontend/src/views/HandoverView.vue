<script setup>
import { useRoute } from 'vue-router'
import MenteeHeader from '../components/MenteeHeader.vue'
import { reactive, ref } from 'vue'
import { toast } from '../lib/toast'
import { api } from '../api/client'
import ReportSource from '../components/ReportSource.vue'
import { copyText } from '../lib/copy'
import { handoverText } from '../lib/reports'
import { saveItem } from '../stores/vault'

// 멘토 교체 인계 요약: 출석 패턴, 과제 수행, 학습 태도, 수강 강의·진도만 넘긴다.
const alias = ref(String(useRoute().params.alias))
const reports = ref([])
const res = ref(null)
const summary = reactive({})
const busy = ref(false)
const error = ref('')
let savedId   // 한 번 저장한 뒤에는 같은 항목을 덮어쓴다

async function build() {
  error.value = ''
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
  return handoverText(summary)   // 허용된 네 항목만, 다음 멘토가 붙여 넣으면 칸별로 나뉘는 형식
}

const copyAll = () => copyText(asText(), '인계 요약')

async function save() {
  try {
    savedId = (await saveItem({ id: savedId, alias: alias.value, formId: 'handover_summary', title: '인계 요약', draft: { ...summary } })).id
    toast('인계 요약을 저장했습니다.')
  } catch (e) {
    error.value = e.message
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
        <button type="button" class="primary" data-test="copy-handover" @click="copyAll">다음 멘토에게 보낼 글 복사</button>
        <button type="button" @click="save">저장</button>
      </div>
      <p class="notice">복사한 글을 이음단이나 운영사무국을 통해 다음 멘토에게 전달해 주세요. 다음 멘토가 사전 연락 화면에 붙여 넣어 두고 종합계획서를 쓸 때 참고합니다.</p>
      <div class="card"><ul><li v-for="r in res.reminders" :key="r">{{ r }}</li></ul></div>
    </template>
  </div>
</template>
