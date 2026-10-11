<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../api/client'
import { reportsFromVault } from '../lib/reports'
import { missingRounds, splitReports } from '../lib/reportSplit'
import { listItems } from '../stores/vault'

// 활동보고서 모으기: 보관함에서 불러오고, 부족하면 플랫폼에서 복사한 보고서를 붙여 넣어 회차별로 나눠 더한다.
// 붙여 넣은 글은 이 브라우저에서 나눈다 (멘티·멘토 이름 칸이 들어 있어 서버로 보내지 않는다).
const props = defineProps({ alias: { type: String, default: '' } })
const emit = defineEmits(['loaded'])
const pasted = ref('')
const reports = ref([])
const status = ref('')
const warnings = ref([])
let items = []

async function fromVault() {
  try {
    items = await listItems(props.alias.trim())
  } catch {
    status.value = '이 브라우저에 저장한 자료를 읽지 못했습니다. 화면을 새로 고친 뒤 다시 시도해 주세요.'
    return
  }
  reports.value = reportsFromVault(items)
  status.value = reports.value.length ? `작성해 둔 활동보고서 ${reports.value.length}건에서 내용을 불러왔습니다.` : '저장해 둔 활동보고서가 없습니다. 회차별 활동보고서를 먼저 작성하거나, 아래에 플랫폼의 보고서를 붙여 넣어 주세요.'
  emit('loaded', { reports: reports.value, items })
}
onMounted(fromVault)

async function fromPaste() {
  try {
    const res = splitReports(pasted.value, (await api.form('activity_report')).fields)
    // 저장해 둔 회차에 붙여 넣은 회차를 더한다 (같은 회차는 붙여 넣은 것을 쓴다)
    const byNo = new Map([...reportsFromVault(items), ...res.sessions].map((r) => [r.session_no, r]))
    reports.value = [...byNo.values()].sort((a, b) => a.session_no - b.session_no)
    const missing = missingRounds(reports.value)
    warnings.value = [...res.warnings, ...(missing.length ? [`빠진 회차가 있습니다: ${missing.join(', ')}회차.`] : [])]
    status.value = `붙여 넣은 글에서 ${res.sessions.length}건을 읽어 모두 ${reports.value.length}건입니다.`
    emit('loaded', { reports: reports.value, items })
  } catch (e) {
    status.value = e.message
  }
}
</script>

<template>
  <div class="card">
    <p v-if="status" role="status" data-test="status">{{ status }}</p>
    <details>
      <summary>저장해 둔 것이 없거나 부족하면: 플랫폼의 활동보고서를 복사해 붙여 넣기</summary>
      <p class="muted">여러 회차를 한 번에 붙여 넣어도 됩니다. 항목 이름(멘토링 일자, 진행 회차 …)이 함께 복사돼야 회차별로 나눌 수 있습니다. 멘티·멘토 이름 칸은 읽지 않고 버립니다.</p>
      <textarea v-model="pasted" rows="6" aria-label="플랫폼에서 복사한 활동보고서" data-test="paste-reports"></textarea>
      <button type="button" class="gap-top" :disabled="!pasted.trim()" data-test="split-reports" @click="fromPaste">회차별로 나누기</button>
    </details>
    <div v-if="warnings.length" class="box warn"><ul><li v-for="w in warnings" :key="w">{{ w }}</li></ul></div>
  </div>
</template>
