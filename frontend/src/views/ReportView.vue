<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '../api/client'
import DraftResult from '../components/DraftResult.vue'
import MenteeHeader from '../components/MenteeHeader.vue'
import SchemaForm from '../components/SchemaForm.vue'
import { emptyInputs, inputFields, toPayload } from '../lib/formFields'
import { menteePath, nextSessionNo, profileFromVault, suggestDate } from '../lib/mentee'
import { toast } from '../lib/toast'
import { listItems, saveItem } from '../stores/vault'

// 한 멘티의 한 회차 활동보고서. 저장한 초안이 있으면 다시 열어 고치고, 없으면 멘티 정보로 칸을 채워 새로 쓴다.
const FORM_ID = 'activity_report'
const route = useRoute()
const alias = String(route.params.alias)
const form = ref(null)
const fields = computed(() => (form.value ? inputFields(form.value) : []))
const values = ref({})
const result = ref(null)
const edited = ref(null)
const busy = ref(false)
const error = ref('')
const filled = ref('')
const savedId = ref(undefined)
const sessionNo = ref(Number(route.params.no) || 0)
let payload = {}

onMounted(async () => {
  try {
    form.value = await api.form(FORM_ID)
    const items = await listItems(alias)
    if (!sessionNo.value) sessionNo.value = nextSessionNo(items)
    const existing = items.filter((x) => x.formId === FORM_ID && Number(x.sessionNo ?? x.inputs?.session_no) === sessionNo.value)
      .sort((a, b) => (a.savedAt < b.savedAt ? 1 : -1))[0]
    if (existing) {
      // 저장한 초안을 다시 연다
      savedId.value = existing.id
      values.value = { ...emptyInputs(fields.value), ...existing.inputs }
      payload = existing.inputs
      result.value = { draft: existing.draft, missing_questions: [], warnings: [], reminders: [], pii_masked: [] }
      edited.value = existing.draft
      return
    }
    const profile = profileFromVault(items)
    const v = emptyInputs(fields.value)
    const done = [`${sessionNo.value}회차`]
    v.session_no = String(sessionNo.value)
    if (profile?.subject) { v.subject = profile.subject; done.push('과목') }
    if (profile?.course) { v.course = profile.course; done.push('강좌') }
    const d = suggestDate(profile?.start_datetime, sessionNo.value)
    if (d) { v.session_date = d; done.push('예상 날짜') }
    values.value = v
    filled.value = `자동으로 채웠습니다: ${done.join(', ')}. 실제와 다르면 고쳐 주세요.`
  } catch (e) {
    error.value = e.message
  }
})

async function submit() {
  error.value = ''
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
    const no = Number(payload.session_no) || sessionNo.value
    const item = await saveItem({ id: savedId.value, alias, formId: FORM_ID, title: `활동보고서 ${no}회차`, sessionNo: no, inputs: payload, draft: edited.value })
    savedId.value = item.id
    toast('저장했습니다.')
  } catch (e) {
    error.value = e.message
  }
}
</script>

<template>
  <div class="shell">
    <MenteeHeader :alias="alias" :title="`활동보고서 ${sessionNo}회차`" />
    <h1>{{ sessionNo }}회차 활동보고서</h1>
    <p class="muted">회차에 있었던 일을 짧게 적으면 보고서 문장으로 다듬어 드립니다. 적지 않은 내용은 만들지 않습니다.</p>
    <div v-if="error" class="box error">{{ error }}</div>
    <p v-if="savedId && result" class="box ask" data-test="reopened">저장해 둔 초안을 다시 열었습니다. 아래에서 고치고 다시 저장하거나, 입력을 바꿔 초안을 새로 만들 수 있습니다.</p>
    <form v-if="form" class="card" @submit.prevent="submit">
      <p v-if="filled" class="box ask" data-test="autofill">{{ filled }}</p>
      <SchemaForm v-model="values" :fields="fields" />
      <p class="notice">멘티 이름·연락처·학교는 쓰지 마세요. 적혀 있으면 AI에 보내기 전에 가립니다.</p>
      <button class="primary" :disabled="busy">{{ busy ? '초안을 만드는 중입니다…' : result ? '초안 다시 만들기' : '초안 만들기' }}</button>
    </form>
    <template v-if="result">
      <h2>초안</h2>
      <DraftResult :form="form" :result="result" @change="edited = $event" />
      <div class="card row">
        <button type="button" class="primary" @click="save">저장</button>
        <router-link :to="menteePath(alias)"><button type="button">{{ alias }}(으)로 돌아가기</button></router-link>
        <span class="notice" style="margin: 0">저장하면 회차 목록에 표시되고, 완료보고서와 인계 요약을 만들 때 쓰입니다.</span>
      </div>
    </template>
  </div>
</template>
