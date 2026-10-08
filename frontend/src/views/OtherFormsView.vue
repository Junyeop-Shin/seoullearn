<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '../api/client'
import AliasInput from '../components/AliasInput.vue'
import DraftResult from '../components/DraftResult.vue'
import SchemaForm from '../components/SchemaForm.vue'
import { emptyInputs, inputFields, toPayload } from '../lib/formFields'
import { saveItem } from '../stores/vault'

// 전용 화면이 없는 서식. forms/ 폴더에 JSON 파일을 추가하면 이 화면에 바로 나온다 (코드 수정 없음).
const DEDICATED = ['activity_report', 'pre_contact', 'plan_initial', 'plan_file', 'completion_report', 'handover_summary']
const route = useRoute()
const list = ref([])
const form = ref(null)
const fields = computed(() => (form.value ? inputFields(form.value) : []))
const values = ref({})
const result = ref(null)
const edited = ref(null)
const alias = ref('')
const error = ref('')
const status = ref('')
const busy = ref(false)

async function load(formId) {
  error.value = status.value = ''
  result.value = form.value = null
  try {
    if (!formId) {
      list.value = (await api.forms()).filter((f) => !DEDICATED.includes(f.form_id))
      return
    }
    form.value = await api.form(formId)
    values.value = emptyInputs(fields.value)
  } catch (e) {
    error.value = e.message
  }
}
watch(() => route.params.formId, load, { immediate: true })

async function submit() {
  error.value = status.value = ''
  busy.value = true
  try {
    result.value = await api.draft(form.value.form_id, toPayload(fields.value, values.value))
    edited.value = result.value.draft
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

async function save() {
  try {
    await saveItem({ alias: alias.value, formId: form.value.form_id, title: form.value.title, inputs: toPayload(fields.value, values.value), draft: edited.value })
    status.value = '보관함에 저장했습니다.'
  } catch (e) {
    status.value = e.message
  }
}
</script>

<template>
  <div class="shell">
    <div v-if="error" class="box error">{{ error }}</div>
    <template v-if="!route.params.formId">
      <h1>기타 서식</h1>
      <p v-if="!list.length" class="muted">추가된 서식이 없습니다.</p>
      <router-link v-for="f in list" :key="f.form_id" :to="`/forms/${f.form_id}`" class="card" style="display: block; text-decoration: none; color: inherit">
        <strong>{{ f.title }}</strong>
      </router-link>
    </template>
    <template v-else-if="form">
      <h1>{{ form.title }}</h1>
      <p class="muted">{{ form.when }}</p>
      <form class="card" @submit.prevent="submit">
        <SchemaForm v-model="values" :fields="fields" />
        <p class="notice">멘티 이름·연락처·학교는 쓰지 마세요. 적혀 있으면 AI에 보내기 전에 가립니다.</p>
        <button class="primary" :disabled="busy">{{ busy ? '만드는 중입니다…' : '확인하기' }}</button>
      </form>
      <template v-if="result">
        <DraftResult :form="form" :result="result" @change="edited = $event" />
        <div class="card">
          <AliasInput v-model="alias" />
          <div class="row"><button type="button" @click="save">보관함에 저장</button><span>{{ status }}</span></div>
        </div>
      </template>
    </template>
  </div>
</template>
