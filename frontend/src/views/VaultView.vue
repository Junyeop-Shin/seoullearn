<script setup>
import { computed, onMounted, ref } from 'vue'
import { PROFILE_FORM } from '../lib/mentee'
import { clearSettings, loadSettings } from '../stores/settings'
import { clearAll, downloadJson, exportAll, importAll, listItems, removeItem } from '../stores/vault'

// 백업·복원: 이 브라우저에만 있는 자료 목록. 백업 파일로 내려받고 복원할 수 있다.
const items = ref([])
const status = ref('')
const failed = ref(false)   // 방금 알린 것이 실패인지
const hasSettings = ref(Object.values(loadSettings()).some(Boolean))   // 멘티가 없어도 멘토 설정(이름, 연락처)이 남아 있으면 지울 수 있어야 한다
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
  downloadJson(data, `seoullearn-vault-${data.exportedAt.slice(0, 10)}.json`)
  failed.value = false
  status.value = `${data.items.length}건을 백업 파일로 내려받았습니다. 파일에 멘티 이름과 문서 내용이 그대로 들어 있으니 안전한 곳에 보관해 주세요.`
}

async function importFile(e) {
  const file = e.target.files[0]
  if (!file) return
  // 같은 항목은 파일의 내용으로 덮어쓴다: 백업한 뒤에 고친 글이 있으면 사라진다
  if (items.value.length && !window.confirm('백업 파일의 내용으로 같은 항목을 바꿉니다. 백업한 뒤에 고친 내용은 사라집니다. 복원할까요?')) return (e.target.value = '')
  failed.value = false
  try {
    const n = await importAll(JSON.parse(await file.text()))
    status.value = `${n}건을 복원했습니다.`
    await refresh()
  } catch (err) {
    failed.value = true
    status.value = err instanceof SyntaxError ? '파일을 읽지 못했습니다. 백업·복원에서 내려받은 파일인지 확인해 주세요.' : err.message
  }
  e.target.value = ''
}

async function remove(id) {
  if (!window.confirm('이 항목을 이 브라우저에서 지웁니다. 백업 파일을 내려받지 않았다면 되돌릴 수 없습니다. 지울까요?')) return
  await removeItem(id)
  await refresh()
}

async function removeAll() {
  if (!window.confirm('등록한 멘티, 저장한 문서, 멘토 설정을 이 브라우저에서 모두 지웁니다. 멘티와 문서는 백업 파일이 있어야 되돌릴 수 있고, 멘토 설정은 백업 파일에 들어 있지 않아 다시 적어야 합니다. 지울까요?')) return
  await clearAll()
  clearSettings()   // 여럿이 쓰는 컴퓨터에 멘토 이름과 연락처가 남지 않게 함께 지운다
  hasSettings.value = false
  failed.value = false
  status.value = '모두 지웠습니다.'
  await refresh()
}
</script>

<template>
  <div class="shell">
    <h1>백업·복원</h1>
    <p class="muted">멘티 정보와 문서는 이 브라우저에만 저장되고 서버로 보내지 않습니다. 브라우저가 오래 쓰지 않은 사이트의 자료를 지울 수 있으니 회기마다 백업 파일을 내려받아 두고, 다른 컴퓨터에서 쓰려면 옮겨 간 곳에서 복원해 주세요.</p>
    <div class="card row">
      <button type="button" class="primary" :disabled="!items.length" @click="exportFile">백업 파일 내려받기</button>
      <button type="button" @click="$refs.file.click()">백업 파일로 복원</button>
      <input ref="file" type="file" accept="application/json,.json" hidden aria-label="백업 파일 고르기" @change="importFile" />
      <span class="grow"></span>
      <button type="button" class="danger" :disabled="!items.length && !hasSettings" @click="removeAll">이 브라우저의 자료 모두 지우기</button>
    </div>
    <p v-if="status" class="box" :class="failed ? 'error' : 'ask'" :role="failed ? 'alert' : 'status'" data-test="vault-status">{{ status }}</p>
    <p v-if="!items.length" class="muted">저장한 자료가 없습니다. 멘티를 등록하면 여기에 쌓입니다.</p>
    <div v-for="(list, alias) in grouped" :key="alias" class="card">
      <strong>{{ alias }}</strong> <span class="tag">{{ list.length }}건</span>
      <table class="gap-top vault"><tbody>
        <tr v-for="x in list" :key="x.id">
          <td>{{ x.title }}</td>
          <td class="muted nowrap" :title="x.savedAt.slice(0, 16).replace('T', ' ')">{{ x.savedAt.slice(0, 10) }}</td>
          <!-- 멘티 정보는 여기서 지우지 않는다: 지우면 멘티가 메뉴에서 사라진다 (멘티를 지우는 것은 멘티 설정에서 한다) -->
          <td v-if="x.formId !== PROFILE_FORM" class="actions">
            <button type="button" class="small danger" @click="remove(x.id)">삭제</button>
          </td>
          <td v-else></td>
        </tr>
      </tbody></table>
    </div>
  </div>
</template>
