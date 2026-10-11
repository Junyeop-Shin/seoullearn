<script setup>
import { reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '../api/client'
import MenteeHeader from '../components/MenteeHeader.vue'
import ReportSource from '../components/ReportSource.vue'
import { copyText } from '../lib/copy'
import { profileFromVault } from '../lib/mentee'
import { TERM_SUMMARY_FORM, activitiesFromVault, goalsFromVault, latestOf } from '../lib/reports'
import { toast } from '../lib/toast'
import { saveItem } from '../stores/vault'

// 완료보고서: 플랫폼에서 멘토가 직접 적는 네 칸(멘토링 내용, 학습목표 대비 성취도, 감성케어 상담, 멘티 요청사항 및 해결과정)의 초안을 만든다.
// 화면을 열면 저장해 둔 종합계획서와 활동보고서로 바로 초안을 쓰고, 멘토는 고치고 덧붙여 칸마다 복사한다. 수행 리스트와 이름·과목은 플랫폼이 채우므로 다루지 않는다.
const FORM_ID = 'completion_report'
const BOXES = [
  { key: 'content', label: '멘토링 내용', hint: '학습 외 습관과 태도, 진로·진학 탐색 내용입니다. 활동보고서에 그런 기록이 있을 때만 초안이 나옵니다.' },
  { key: 'achievement', label: '학습목표 대비 성취도', hint: '출결, 인강 수강, 과제 수행, 학습 진도를 회차 기록으로 정리했습니다.' },
  { key: 'emotional_care', label: '감성케어 상담', hint: '정서·가정 이야기는 활동보고서에 남기지 않으므로 초안을 만들지 않습니다. 적을 내용이 있으면 직접 써 주세요.' },
  { key: 'requests', label: '멘티 요청사항 및 해결과정', hint: '활동보고서의 기타·건의사항에 적은 요청이 있을 때만 초안이 나옵니다.' },
]
defineOptions({ inheritAttrs: false })   // 멘티 화면이 모든 단계에 같은 값을 넘긴다: 안 쓰는 값이 화면 요소에 붙지 않게 한다
defineProps({ embedded: { type: Boolean, default: false } })
const emit = defineEmits(['saved'])
const alias = String(useRoute().params.alias)
const text = reactive(Object.fromEntries(BOXES.map((b) => [b.key, ''])))
const ready = ref(false)       // 초안을 만들었거나 저장해 둔 것을 열었다
const busy = ref(false)
const error = ref('')
const notes = ref([])
const reports = ref([])   // 초안의 재료가 되는 활동보고서
let goals = [], activities = [], duration = '', savedId

// 초안의 항목은 서식의 작성 예시처럼 줄마다 '- '를 붙인다
const asText = (v) => (Array.isArray(v) ? v.map((x) => `- ${String(x).replace(/^[-·•]\s*/, '')}`).join('\n') : String(v || ''))
// 긴 글도 한눈에 보이게 글의 양에 맞춰 칸을 키운다
const rowsOf = (t) => Math.max(5, t.split('\n').reduce((n, line) => n + Math.max(1, Math.ceil(line.length / 58)), 1))

async function loaded({ reports: r, items }) {
  reports.value = r
  goals = goalsFromVault(items)
  activities = activitiesFromVault(items)   // 친화·성장활동 기록도 초안의 참고 자료다
  duration = profileFromVault(items)?.duration || duration
  if (ready.value) return   // 붙여 넣어 회차를 더했을 때는 적어 둔 글을 그대로 둔다 (다시 만들려면 버튼을 누른다)
  // 이번 회기에 저장해 둔 완료보고서가 있으면 그것을 연다 (지난 회기 것은 회기 요약보다 먼저 저장된 것이다)
  const since = latestOf(items, TERM_SUMMARY_FORM)?.savedAt || ''
  const mine = items.find((x) => x.formId === FORM_ID && x.savedAt > since)
  if (mine) {
    savedId = mine.id
    for (const b of BOXES) text[b.key] = asText(mine.draft?.[b.key])
    ready.value = true
  } else if (r.length) await draft()
}

async function draft() {
  error.value = ''
  busy.value = true
  try {
    const res = await api.draft(FORM_ID, {}, { reports: reports.value, plan_goal: goals, activities, duration })
    // 아동 안전 신호가 있으면 서버가 초안을 만들지 않고 운영사무국 안내만 돌려준다
    if (!Object.keys(res.draft).length) throw new Error(res.warnings[0] || '초안을 만들지 못했습니다.')
    for (const b of BOXES) text[b.key] = asText(res.draft[b.key])
    notes.value = [...res.warnings, ...res.reminders]
    ready.value = true
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
function redraft() {
  if (window.confirm('활동보고서로 초안을 다시 만듭니다. 지금 칸에 적힌 글은 새 초안으로 바뀝니다. 계속할까요?')) draft()
}

async function save() {
  error.value = ''
  try {
    savedId = (await saveItem({ id: savedId, alias, formId: FORM_ID, title: '완료보고서', draft: { ...text } })).id
    toast('완료보고서를 저장했습니다.')
    emit('saved')
  } catch (e) {
    error.value = e.message
  }
}
</script>

<template>
  <div :class="{ shell: !embedded }">
    <template v-if="!embedded">
      <MenteeHeader :alias="alias" title="완료보고서" />
      <h1>완료보고서 작성</h1>
    </template>
    <p class="muted">저장해 둔 종합계획서와 활동보고서로 초안을 써 두었습니다. 고치고 덧붙인 뒤 칸마다 [복사]해 플랫폼의 같은 칸에 붙여 넣어 주세요. 수행 리스트는 플랫폼이 자동으로 채웁니다.</p>
    <div v-if="error" class="box error">{{ error }}</div>
    <ReportSource :alias="alias" @loaded="loaded" />
    <p v-if="busy" class="card muted" aria-live="polite" data-test="drafting">초안을 쓰는 중입니다…</p>
    <form v-if="ready" class="card plan-form" data-test="completion-form" @submit.prevent="save">
      <fieldset :disabled="busy">
        <div v-for="b in BOXES" :key="b.key" class="item">
          <div class="head"><strong>{{ b.label }}</strong><button type="button" class="small" :disabled="!text[b.key].trim()" :data-copy="b.key" @click="copyText(text[b.key], b.label)">복사</button></div>
          <textarea v-model="text[b.key]" :rows="rowsOf(text[b.key])" :aria-label="b.label" :data-draft="b.key"></textarea>
          <span class="notice">{{ b.hint }}</span>
        </div>
        <div v-if="notes.length" class="box warn" data-test="notes"><ul><li v-for="n in notes" :key="n">{{ n }}</li></ul></div>
        <div class="row">
          <button class="primary" data-test="save">저장</button>
          <button type="button" :disabled="!reports.length" data-test="redraft" @click="redraft">초안 다시 만들기</button>
        </div>
      </fieldset>
    </form>
  </div>
</template>
