<script setup>
import { useRoute } from 'vue-router'
import MenteeHeader from '../components/MenteeHeader.vue'
import { computed, onMounted, ref, watch } from 'vue'
import { api } from '../api/client'
import DraftResult from '../components/DraftResult.vue'
import ReportSource from '../components/ReportSource.vue'
import SchemaForm from '../components/SchemaForm.vue'
import { emptyInputs, inputFields, toPayload } from '../lib/formFields'
import { fillValues, profileFromVault } from '../lib/mentee'
import { TERM_SUMMARY_FORM, goalsFromVault, latestOf } from '../lib/reports'
import { toast } from '../lib/toast'
import { loadSettings } from '../stores/settings'
import { saveItem } from '../stores/vault'

// 완료보고서: 활동보고서 16건 → 수행 리스트(자동), 멘토링 내용·성취도 초안. 감성케어 칸은 멘토가 쓴 것만 쓴다.
const FORM_ID = 'completion_report'
defineOptions({ inheritAttrs: false })   // 멘티 화면이 모든 단계에 같은 값을 넘긴다: 안 쓰는 값이 화면 요소에 붙지 않게 한다
defineProps({ embedded: { type: Boolean, default: false } })
const emit = defineEmits(['saved'])
const fill = ref({})
const form = ref(null)
const fields = computed(() => (form.value ? inputFields(form.value) : []))
const values = ref({})
const alias = ref(String(useRoute().params.alias))
const reports = ref([])
const goals = ref('')
const result = ref(null)
const edited = ref(null)
const busy = ref(false)
const error = ref('')
const duration = ref('')   // 회당 학습시간: 시간확대(120분)면 한 회기가 8회차다
const mine = ref(null)     // 이번 회기에 저장해 둔 완료보고서 (다시 열어 고친다)

onMounted(async () => {
  try {
    form.value = await api.form(FORM_ID)
    values.value = emptyInputs(fields.value)
  } catch (e) {
    error.value = e.message
  }
})

function loaded({ reports: r, items }) {
  reports.value = r
  const profile = profileFromVault(items)
  fill.value = fillValues(profile, loadSettings())
  duration.value = profile?.duration || duration.value
  const g = goalsFromVault(items)
  if (g.length && !goals.value.trim()) goals.value = g.join('\n')   // 고쳐 둔 목표는 덮지 않는다
  // 지난 회기의 완료보고서는 회기 요약보다 먼저 저장된 것이다: 그 뒤에 저장한 것만 이번 회기 것으로 본다
  const since = latestOf(items, TERM_SUMMARY_FORM)?.savedAt || ''
  mine.value = items.find((x) => x.formId === FORM_ID && x.savedAt > since) || null
}
// 저장해 둔 완료보고서가 있으면 직접 적은 내용과 초안을 다시 보여 준다 (양식을 받은 뒤에 채운다)
watch([form, mine], () => {
  if (!form.value || !mine.value || result.value) return
  values.value = { ...values.value, ...Object.fromEntries(Object.entries(mine.value.inputs || {}).map(([k, v]) => [k, Array.isArray(v) ? v.join('\n') : v])) }
  result.value = { draft: mine.value.draft, warnings: [], missing_questions: [], reminders: [] }
  edited.value = mine.value.draft
})

async function submit() {
  error.value = ''
  busy.value = true
  try {
    const plan_goal = goals.value.split('\n').map((x) => x.trim()).filter(Boolean)
    const res = await api.draft(FORM_ID, toPayload(fields.value, values.value), { reports: reports.value, plan_goal, duration: duration.value })
    // 아동 안전 신호가 있으면 서버가 초안을 만들지 않고 운영사무국 안내만 돌려준다: 그 안내를 보여 주고 빈 초안은 두지 않는다
    if (!Object.keys(res.draft).length) throw new Error(res.warnings[0] || '초안을 만들지 못했습니다.')
    result.value = res
    edited.value = res.draft
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

async function save() {
  error.value = ''
  try {
    mine.value = await saveItem({ id: mine.value?.id, alias: alias.value, formId: FORM_ID, title: '완료보고서', inputs: toPayload(fields.value, values.value), draft: edited.value })
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
    <p class="muted">회기를 마친 뒤 작성합니다. 저장해 둔 활동보고서와 종합계획서를 불러와, 회차별 일자와 시간은 그대로 옮기고 내용과 성취도는 기록에 있는 것만으로 초안을 씁니다.</p>
    <div v-if="error" class="box error">{{ error }}</div>
    <h3>활동보고서</h3>
    <ReportSource :alias="alias" @loaded="loaded" />
    <h3>직접 적을 내용</h3>
    <form v-if="form" class="card" @submit.prevent="submit">
      <label class="field"><span class="name">학습목표 (종합계획서에 적은 것)</span>
        <textarea v-model="goals" placeholder="한 줄에 하나씩. 종합계획서를 보관함에 저장해 두었다면 자동으로 채워집니다."></textarea>
      </label>
      <SchemaForm v-model="values" :fields="fields" />
      <p class="notice">감성케어 상담 칸은 활동보고서에서 가져오지 않습니다. 적을 내용이 있으면 여기에 직접 써 주세요.</p>
      <button class="primary" :disabled="busy || !reports.length">{{ busy ? '초안을 만드는 중입니다…' : '완료보고서 초안 만들기' }}</button>
    </form>
    <template v-if="result && form">
      <h3>초안</h3>
      <DraftResult :form="form" :result="result" :fill="fill" @change="edited = $event" />
      <div class="row"><button type="button" class="primary" data-test="save" @click="save">저장</button></div>
    </template>
  </div>
</template>
