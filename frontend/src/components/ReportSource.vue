<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../api/client'
import { reportsFromVault } from '../lib/reports'
import { listItems } from '../stores/vault'

// 활동보고서 모으기: 보관함에서 불러오거나, 플랫폼에서 복사한 보고서를 붙여 넣어 회차별로 나눈다.
const props = defineProps({ alias: { type: String, default: '' } })
const emit = defineEmits(['loaded'])
const pasted = ref('')
const reports = ref([])
const status = ref('')
const warnings = ref([])
const busy = ref(false)

async function fromVault() {
  warnings.value = []
  const items = await listItems(props.alias.trim())
  reports.value = reportsFromVault(items)
  status.value = reports.value.length ? `저장해 둔 활동보고서 ${reports.value.length}건을 불러왔습니다.` : '저장해 둔 활동보고서가 없습니다. 회차별 활동보고서를 먼저 작성하거나, 아래에 플랫폼의 보고서를 붙여 넣어 주세요.'
  emit('loaded', { reports: reports.value, items })
}
onMounted(fromVault)

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
    <p v-if="status" data-test="status">{{ status }}</p>
    <p v-if="reports.length" class="muted">회차: {{ reports.map((r) => r.session_no).join(', ') }}</p>
    <details>
      <summary>저장해 둔 것이 없거나 부족하면: 플랫폼의 활동보고서를 복사해 붙여 넣기</summary>
      <p class="muted">여러 회차를 한 번에 붙여 넣어도 됩니다. 항목 이름(멘토링 일자, 진행 회차 …)이 함께 복사돼야 회차별로 나눌 수 있습니다. 멘티·멘토 이름 칸은 읽지 않고 버립니다.</p>
      <textarea v-model="pasted" rows="6"></textarea>
      <button type="button" style="margin-top: 6px" :disabled="!pasted.trim() || busy" @click="fromPaste">회차별로 나누기</button>
    </details>
    <div v-if="warnings.length" class="box warn"><ul><li v-for="w in warnings" :key="w">{{ w }}</li></ul></div>
  </div>
</template>
