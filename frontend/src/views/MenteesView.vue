<script setup>
import { onMounted, reactive, ref } from 'vue'
import { PROFILE_FIELDS, PROFILE_FORM, emptyProfile, getCurrentAlias, nextSessionNo, profileFromVault, setCurrentAlias } from '../lib/mentee'
import { COURSE_ALIAS } from '../lib/reports'
import { toast } from '../lib/toast'
import { listAliases, listItems, saveItem } from '../stores/vault'

// 내 멘티: 멘티별로 한 번 적어 두는 정보. 보고서와 계획서 화면이 이 값을 불러와 다시 입력하지 않게 한다.
const mentees = ref([])   // [{ alias, profile, reports, next }]
const alias = ref('')
const profile = reactive(emptyProfile())
const editingId = ref(undefined)
const error = ref('')

async function refresh() {
  const out = []
  for (const a of (await listAliases()).filter((x) => x !== COURSE_ALIAS)) {
    const items = await listItems(a)
    out.push({ alias: a, profile: profileFromVault(items), reports: items.filter((x) => x.formId === 'activity_report').length, next: nextSessionNo(items) })
  }
  mentees.value = out
}

async function edit(a) {
  alias.value = a
  setCurrentAlias(a)
  const found = profileFromVault(await listItems(a))
  Object.assign(profile, emptyProfile(), found || {})
  editingId.value = found?._id
  delete profile._id
}

function startNew() {
  alias.value = ''
  Object.assign(profile, emptyProfile())
  editingId.value = undefined
}

async function save() {
  error.value = ''
  try {
    const item = await saveItem({ id: editingId.value, alias: alias.value, formId: PROFILE_FORM, title: '멘티 정보', draft: { ...profile } })
    editingId.value = item.id
    setCurrentAlias(item.alias)
    toast('멘티 정보를 저장했습니다.')
    await refresh()
  } catch (e) {
    error.value = e.message
  }
}

onMounted(async () => {
  await refresh()
  const current = getCurrentAlias()
  if (current && mentees.value.some((m) => m.alias === current)) await edit(current)
})
</script>

<template>
  <div class="shell">
    <h1>내 멘티</h1>
    <p class="muted">멘티마다 과목, 강좌, 일정을 한 번 적어 두면 활동보고서와 종합계획서 화면에서 다시 입력하지 않아도 됩니다. 이 브라우저에만 저장되고 서버로 보내지 않습니다.</p>

    <div v-if="mentees.length" class="card" data-test="mentee-list">
      <table>
        <tr><th>별칭</th><th>과목</th><th>일정</th><th>저장한 활동보고서</th><th></th></tr>
        <tr v-for="m in mentees" :key="m.alias">
          <td><strong>{{ m.alias }}</strong></td>
          <td>{{ m.profile?.subject || '-' }} <span v-if="m.profile?.mode" class="tag">{{ m.profile.mode }}</span></td>
          <td>{{ m.profile?.weekday ? `매주 ${m.profile.weekday}요일` : '-' }}</td>
          <td>{{ m.reports }}건 <span class="muted">(다음 {{ m.next }}회차)</span></td>
          <td style="text-align: right"><button type="button" class="small" @click="edit(m.alias)">{{ m.profile ? '수정' : '정보 입력' }}</button></td>
        </tr>
      </table>
    </div>

    <h2>{{ editingId ? '멘티 정보 수정' : '멘티 정보 입력' }}</h2>
    <form class="card" @submit.prevent="save">
      <label class="field"><span class="name">멘티 별칭<span class="req">*</span></span>
        <input v-model="alias" placeholder="예: 수학 고2 A" maxlength="30" required data-profile="alias" />
        <span class="notice">실명을 쓰지 마세요. 과목처럼 본인만 알아볼 수 있는 이름을 씁니다.</span>
      </label>
      <div class="form-grid">
        <label v-for="f in PROFILE_FIELDS" :key="f.key" class="field" :class="{ wide: f.wide }">
          <span class="name">{{ f.label }}</span>
          <select v-if="f.control === 'select'" v-model="profile[f.key]" :data-profile="f.key">
            <option value="">선택해 주세요</option><option v-for="o in f.options" :key="o" :value="o">{{ o }}</option>
          </select>
          <textarea v-else-if="f.control === 'textarea'" v-model="profile[f.key]" rows="2" :data-profile="f.key"></textarea>
          <input v-else v-model="profile[f.key]" :type="f.control" :placeholder="f.example ? `예: ${f.example}` : ''" :data-profile="f.key" />
          <span v-if="f.help" class="notice">{{ f.help }}</span>
        </label>
      </div>
      <div class="box warn">멘티의 이름, 학년, 학교, 연락처, 가정 사정은 적지 마세요. 이 화면에는 그런 칸이 없습니다.</div>
      <div v-if="error" class="box error">{{ error }}</div>
      <div class="row">
        <button class="primary">저장</button>
        <button v-if="editingId || alias" type="button" @click="startNew">새 멘티 입력</button>
      </div>
    </form>
  </div>
</template>
