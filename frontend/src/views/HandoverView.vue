<script setup>
import { reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '../api/client'
import MenteeHeader from '../components/MenteeHeader.vue'
import ReportSource from '../components/ReportSource.vue'
import { copyText } from '../lib/copy'
import { HANDOVER_ITEMS, handoverText, myHandover } from '../lib/reports'
import { toast } from '../lib/toast'
import { saveItem } from '../stores/vault'

// 멘토 교체 인계 요약: 출석 패턴, 과제 수행, 학습 태도, 수강 강의·진도만 넘긴다.
// 저장해 둔 요약이 있으면 그것을 연다 (볼 때마다 AI를 다시 부르지 않고, 고쳐 둔 글이 남는다).
const alias = String(useRoute().params.alias)
const reports = ref([])
const res = ref(null)          // 방금 만든 요약에 딸린 안내 (경고, 가린 정보)
const summary = reactive(Object.fromEntries(HANDOVER_ITEMS.map(([k]) => [k, ''])))
const ready = ref(false)       // 요약이 칸에 들어 있다 (저장해 둔 것을 열었거나 방금 만들었다)
const busy = ref(false)
const error = ref('')
let savedId   // 같은 항목을 덮어쓴다

function loaded({ reports: r, items }) {
  reports.value = r
  if (ready.value) return
  const mine = myHandover(items)   // 내가 만든 요약만 연다. 이전 멘토에게 받아 붙여 넣은 글은 사전 연락 화면의 것이다
  if (!mine) return
  savedId = mine.id
  for (const [k] of HANDOVER_ITEMS) summary[k] = mine.draft?.[k] || ''
  ready.value = true
}

async function build() {
  if (ready.value && !window.confirm('활동보고서로 인계 요약을 다시 만듭니다. 지금 칸에 적힌 글은 새 요약으로 바뀝니다. 계속할까요?')) return
  error.value = ''
  busy.value = true
  try {
    res.value = await api.handover(reports.value)
    for (const [k] of HANDOVER_ITEMS) summary[k] = res.value.summary[k] || ''
    ready.value = true
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

const copyAll = () => copyText(handoverText(summary), '인계 요약')   // 허용된 네 항목만, 다음 멘토가 붙여 넣으면 칸별로 나뉘는 형식

async function save() {
  try {
    savedId = (await saveItem({ id: savedId, alias, formId: 'handover_summary', title: '인계 요약', draft: { ...summary } })).id
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
    <p class="muted">멘토가 바뀔 때 자치구 이음단을 통해 다음 멘토에게 넘길 내용입니다. 아래 네 가지만 만들고, 성적·이해도 같은 학업 수준과 정서·상담 내용은 넣지 않습니다.</p>
    <div v-if="error" class="box error" role="alert">{{ error }}</div>
    <ReportSource :alias="alias" @loaded="loaded" />
    <button type="button" :class="{ primary: !ready }" :disabled="busy || !reports.length" data-test="build-handover" @click="build">{{ busy ? '요약을 만드는 중…' : ready ? '인계 요약 다시 만들기' : '인계 요약 만들기' }}</button>
    <template v-if="res">
      <div v-if="res.warnings.length" class="box warn" data-test="warnings"><ul><li v-for="w in res.warnings" :key="w">{{ w }}</li></ul></div>
      <p v-if="res.pii_masked.length" class="notice">AI에 보내기 전에 가린 정보: {{ res.pii_masked.join(', ') }}</p>
    </template>
    <template v-if="ready">
      <label v-for="[k, label] in HANDOVER_ITEMS" :key="k" class="field">
        <span class="name">{{ label }}</span>
        <textarea v-model="summary[k]" :data-summary="k"></textarea>
      </label>
      <div class="row">
        <button type="button" class="primary" data-test="copy-handover" @click="copyAll">이음단에 보낼 글 복사</button>
        <button type="button" data-test="save-handover" @click="save">저장</button>
      </div>
      <p class="notice">복사한 글은 다음 멘토에게 직접 보내지 말고 자치구 이음단에 보내 주세요. 이음단이 확인한 뒤 다음 멘토에게 전달합니다. 다음 멘토가 사전 연락 화면에 붙여 넣어 두고 종합계획서를 쓸 때 참고합니다.</p>
      <div v-if="res?.reminders?.length" class="card"><ul><li v-for="r in res.reminders" :key="r">{{ r }}</li></ul></div>
    </template>
  </div>
</template>
