<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { api } from '../api/client'
import AliasInput from '../components/AliasInput.vue'
import DraftResult from '../components/DraftResult.vue'
import SchemaForm from '../components/SchemaForm.vue'
import { emptyInputs, inputFields, toPayload } from '../lib/formFields'
import { nextSessionNo, profileFromVault, suggestDate } from '../lib/mentee'
import { listItems, saveItem } from '../stores/vault'

// 활동보고서 작성. 입력 칸은 양식 스키마(GET /api/forms/activity_report)로 그린다.
const FORM_ID = 'activity_report'
const form = ref(null)
const fields = computed(() => (form.value ? inputFields(form.value) : []))
const values = ref({})
const alias = ref('')
const result = ref(null)
const edited = ref(null)
const busy = ref(false)
const error = ref('')
const saved = ref('')
const filled = ref('')
let payload = {}

// 멘티를 고르면 내 멘티에 적어 둔 값과 다음 회차를 채운다. 이미 적은 칸은 건드리지 않는다.
async function autofill() {
  filled.value = ''
  if (!form.value || !alias.value.trim()) return
  const items = await listItems(alias.value.trim())
  const profile = profileFromVault(items)
  const no = nextSessionNo(items)
  const next = { ...values.value }
  const done = []
  const put = (key, value, label) => {
    if (value && !String(next[key] ?? '').trim()) {
      next[key] = String(value)
      done.push(label)
    }
  }
  if (profile) {
    put('subject', profile.subject, '과목')
    put('course', profile.course, '강좌')
  }
  if (profile || items.length) {
    put('session_no', no, `${no}회차`)
    put('session_date', suggestDate(profile?.start_datetime, no), '예상 날짜')
  }
  values.value = next
  if (done.length) filled.value = `멘티 정보에서 채웠습니다: ${done.join(', ')}. 실제와 다르면 고쳐 주세요.`
}
watch(alias, autofill)

onMounted(async () => {
  try {
    form.value = await api.form(FORM_ID)
    values.value = emptyInputs(fields.value)
    await autofill()
  } catch (e) {
    error.value = e.message
  }
})

async function submit() {
  error.value = saved.value = ''
  busy.value = true
  try {
    payload = toPayload(fields.value, values.value)
    result.value = await api.draft(FORM_ID, payload)
    edited.value = result.value.draft
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

async function save() {
  try {
    const no = Number(payload.session_no) || null
    await saveItem({ alias: alias.value, formId: FORM_ID, title: `활동보고서${no ? ` ${no}회차` : ''}`, sessionNo: no, inputs: payload, draft: edited.value })
    saved.value = '보관함에 저장했습니다.'
  } catch (e) {
    saved.value = e.message
  }
}
</script>

<template>
  <div class="shell">
    <h1>활동보고서 작성</h1>
    <p class="muted">회차에 있었던 일을 짧게 적으면 보고서 문장으로 다듬어 드립니다. 적지 않은 내용은 만들지 않습니다.</p>
    <div v-if="error" class="box error">{{ error }}</div>
    <form v-if="form" class="card" @submit.prevent="submit">
      <AliasInput v-model="alias" />
      <p v-if="filled" class="box ask" data-test="autofill">{{ filled }}</p>
      <SchemaForm v-model="values" :fields="fields" />
      <p class="notice">멘티 이름·연락처·학교는 쓰지 마세요. 적혀 있으면 AI에 보내기 전에 가립니다.</p>
      <button class="primary" :disabled="busy">{{ busy ? '초안을 만드는 중입니다…' : '초안 만들기' }}</button>
    </form>
    <template v-if="result">
      <h2>초안</h2>
      <DraftResult :form="form" :result="result" @change="edited = $event" />
      <div class="card">
        <div class="row"><button type="button" class="primary" @click="save">보관함에 저장</button><span>{{ saved }}</span></div>
        <p class="notice">저장해 두면 완료보고서와 인계 요약을 만들 때 불러올 수 있고, 다음 회차 번호가 자동으로 채워집니다.</p>
      </div>
    </template>
  </div>
</template>
