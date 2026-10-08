<script setup>
import { computed, onMounted, ref } from 'vue'
import { toText } from '../lib/formFields'
import { clearAll, exportAll, importAll, listItems, removeItem } from '../stores/vault'

// 보관함: 이 브라우저에만 있는 초안 목록. 파일로 내보내고 가져올 수 있다.
const items = ref([])
const status = ref('')
const open = ref('')
const grouped = computed(() => {
  const g = {}
  for (const x of items.value) (g[x.alias] ||= []).push(x)
  return g
})

async function refresh() {
  items.value = await listItems()
}
onMounted(refresh)

async function exportFile() {
  const data = await exportAll()
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }))
  const a = document.createElement('a')
  a.href = url
  a.download = `seoullearn-vault-${data.exportedAt.slice(0, 10)}.json`
  a.click()
  URL.revokeObjectURL(url)
  status.value = `${data.items.length}건을 파일로 내보냈습니다. 파일에는 초안 내용이 그대로 들어 있으니 안전한 곳에 보관해 주세요.`
}

async function importFile(e) {
  const file = e.target.files[0]
  if (!file) return
  try {
    const n = await importAll(JSON.parse(await file.text()))
    status.value = `${n}건을 가져왔습니다.`
    await refresh()
  } catch (err) {
    status.value = err instanceof SyntaxError ? '파일을 읽지 못했습니다. 이 도구에서 내보낸 파일인지 확인해 주세요.' : err.message
  }
  e.target.value = ''
}

async function remove(id) {
  await removeItem(id)
  await refresh()
}

async function removeAll() {
  if (!window.confirm('보관함의 모든 초안을 지웁니다. 되돌릴 수 없습니다. 계속할까요?')) return
  await clearAll()
  status.value = '보관함을 비웠습니다.'
  await refresh()
}
</script>

<template>
  <div class="shell">
    <h1>보관함</h1>
    <p class="muted">초안은 이 브라우저 안에만 저장되고 서버로 보내지 않습니다. 브라우저 데이터를 지우거나 다른 기기에서 쓰려면 파일로 내보내 옮겨 주세요.</p>
    <div class="card row">
      <button type="button" :disabled="!items.length" @click="exportFile">파일로 내보내기</button>
      <label><input type="file" accept="application/json,.json" style="display: none" @change="importFile" /><span class="mini" style="cursor: pointer">파일에서 가져오기</span></label>
      <span style="flex: 1"></span>
      <button type="button" class="danger" :disabled="!items.length" @click="removeAll">보관함 전체 삭제</button>
    </div>
    <p v-if="status">{{ status }}</p>
    <p v-if="!items.length" class="muted">저장된 초안이 없습니다.</p>
    <div v-for="(list, alias) in grouped" :key="alias" class="card">
      <strong>{{ alias }}</strong> <span class="tag">{{ list.length }}건</span>
      <table style="margin-top: 6px">
        <tr v-for="x in list" :key="x.id">
          <td>{{ x.title }}</td>
          <td class="muted">{{ x.savedAt.slice(0, 16).replace('T', ' ') }}</td>
          <td style="text-align: right">
            <button type="button" class="small" @click="open = open === x.id ? '' : x.id">{{ open === x.id ? '닫기' : '보기' }}</button>
            <button type="button" class="small danger" @click="remove(x.id)">삭제</button>
          </td>
        </tr>
      </table>
      <template v-for="x in list" :key="x.id + 'v'">
        <div v-if="open === x.id" class="mini" style="margin-top: 8px">
          <div v-for="(v, k) in x.draft" :key="k" style="margin: 4px 0"><span class="t">{{ k }}</span><span style="white-space: pre-wrap">{{ toText(v) }}</span></div>
        </div>
      </template>
    </div>
  </div>
</template>
