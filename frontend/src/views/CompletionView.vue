<script setup>
import { useRoute } from 'vue-router'
import MenteeHeader from '../components/MenteeHeader.vue'
import { computed, onMounted, ref } from 'vue'
import { api } from '../api/client'
import DraftResult from '../components/DraftResult.vue'
import ReportSource from '../components/ReportSource.vue'
import SchemaForm from '../components/SchemaForm.vue'
import { emptyInputs, inputFields, toPayload } from '../lib/formFields'
import { goalsFromVault } from '../lib/reports'
import { saveItem } from '../stores/vault'

// 완료보고서: 활동보고서 16건 → 수행 리스트(자동), 멘토링 내용·성취도 초안. 감성케어 칸은 멘토가 쓴 것만 쓴다.
const FORM_ID = 'completion_report'
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
const saved = ref('')

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
  const g = goalsFromVault(items)
  if (g.length) goals.value = g.join('\n')
}

async function submit() {
  error.value = saved.value = ''
  busy.value = true
  try {
    const plan_goal = goals.value.split('\n').map((x) => x.trim()).filter(Boolean)
    result.value = await api.draft(FORM_ID, toPayload(fields.value, values.value), { reports: reports.value, plan_goal })
    edited.value = result.value.draft
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

async function save() {
  try {
    await saveItem({ alias: alias.value, formId: FORM_ID, title: '완료보고서', inputs: toPayload(fields.value, values.value), draft: edited.value })
    saved.value = '보관함에 저장했습니다.'
  } catch (e) {
    saved.value = e.message
  }
}
</script>

<template>
  <div class="shell">
    <MenteeHeader :alias="alias" title="완료보고서" />
    <h1>완료보고서 작성</h1>
    <p class="muted">16회차를 마친 뒤 작성합니다. 회차별 일자와 시간은 활동보고서에서 그대로 옮기고, 내용과 성취도는 기록에 있는 것만으로 초안을 씁니다.</p>
    <div v-if="error" class="box error">{{ error }}</div>
    <h2>① 활동보고서</h2>
    <ReportSource :alias="alias" @loaded="loaded" />
    <h2>② 직접 적을 내용</h2>
    <form v-if="form" class="card" @submit.prevent="submit">
      <label class="field"><span class="name">학습목표 (종합계획서에 적은 것)</span>
        <textarea v-model="goals" placeholder="한 줄에 하나씩. 종합계획서를 보관함에 저장해 두었다면 자동으로 채워집니다."></textarea>
      </label>
      <SchemaForm v-model="values" :fields="fields" />
      <p class="notice">감성케어 상담 칸은 활동보고서에서 가져오지 않습니다. 적을 내용이 있으면 여기에 직접 써 주세요.</p>
      <button class="primary" :disabled="busy || !reports.length">{{ busy ? '초안을 만드는 중입니다…' : '완료보고서 초안 만들기' }}</button>
    </form>
    <template v-if="result">
      <h2>초안</h2>
      <DraftResult :form="form" :result="result" @change="edited = $event" />
      <div class="row"><button type="button" @click="save">보관함에 저장</button><span>{{ saved }}</span></div>
    </template>
  </div>
</template>
