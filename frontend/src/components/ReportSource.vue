<script setup>
import { ref } from 'vue'
import { api } from '../api/client'
import { reportsFromVault } from '../lib/reports'
import { listItems } from '../stores/vault'
import AliasInput from './AliasInput.vue'

// 활동보고서 모으기: 보관함에서 불러오거나, 플랫폼에서 복사한 보고서를 붙여 넣어 회차별로 나눈다.
const props = defineProps({ alias: { type: String, default: '' } })
const emit = defineEmits(['update:alias', 'loaded'])
const pasted = ref('')
const reports = ref([])
const status = ref('')
const warnings = ref([])
const busy = ref(false)

async function fromVault() {
  warnings.value = []
  const items = await listItems(props.alias.trim())
  reports.value = reportsFromVault(items)
  status.value = reports.value.length ? `보관함에서 활동보고서 ${reports.value.length}건을 불러왔습니다.` : '이 별칭으로 저장된 활동보고서가 없습니다.'
  emit('loaded', { reports: reports.value, items })
}

async function fromPaste() {
  busy.value = true
  try {
    const res = await api.splitReports(pasted.value)
    reports.value = res.sessions
    warnings.value = res.warnings
    status.value = `붙여 넣은 글에서 활동보고서 ${res.sessions.length}건을 읽었습니다.`
    emit('loaded', { reports: reports.value, items: [] })
  } catch (e) {
    status.value = e.message
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="card">
    <AliasInput :model-value="alias" @update:model-value="$emit('update:alias', $event)" />
    <button type="button" class="primary" :disabled="!alias.trim()" @click="fromVault">보관함에서 활동보고서 불러오기</button>
    <details style="margin-top: 10px">
      <summary>보관함에 없으면: 플랫폼의 활동보고서를 복사해 붙여 넣기</summary>
      <p class="muted">여러 회차를 한 번에 붙여 넣어도 됩니다. 항목 이름(멘토링 일자, 진행 회차 …)이 함께 복사돼야 회차별로 나눌 수 있습니다. 멘티·멘토 이름 칸은 읽지 않고 버립니다.</p>
      <textarea v-model="pasted" rows="6"></textarea>
      <button type="button" style="margin-top: 6px" :disabled="!pasted.trim() || busy" @click="fromPaste">회차별로 나누기</button>
    </details>
    <p v-if="status" data-test="status">{{ status }}</p>
    <p v-if="reports.length" class="muted">회차: {{ reports.map((r) => r.session_no).join(', ') }}</p>
    <div v-if="warnings.length" class="box warn"><ul><li v-for="w in warnings" :key="w">{{ w }}</li></ul></div>
  </div>
</template>
