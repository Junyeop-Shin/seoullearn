<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { PROFILE_FORM, docStatus, emptyProfile, menteePath, nextStep, profileFromVault } from '../lib/mentee'
import { COURSE_ALIAS } from '../lib/reports'
import { toast } from '../lib/toast'
import { importAll, listAliases, listItems, saveItem } from '../stores/vault'

// 내 멘티: 멘티 목록. 멘티를 누르면 그 멘티의 작업 공간으로 간다.
const router = useRouter()
const mentees = ref([])
const alias = ref('')
const error = ref('')

async function refresh() {
  const out = []
  for (const a of (await listAliases()).filter((x) => x !== COURSE_ALIAS)) {
    const items = await listItems(a)
    const profile = profileFromVault(items)
    out.push({ alias: a, profile, status: docStatus(items), next: nextStep(items, profile) })
  }
  mentees.value = out
}
onMounted(refresh)

// 이름을 정하지 않으면 '멘티 1', '멘티 2'처럼 붙인다
function autoName() {
  let n = mentees.value.length + 1
  while (mentees.value.some((m) => m.alias === `멘티 ${n}`)) n += 1
  return `멘티 ${n}`
}

// 써 보기용 예시 자료 (가상 멘티 4명). 이 브라우저 보관함에만 들어간다
async function loadSamples() {
  try {
    const res = await fetch('/demo_vault.json')
    if (!res.ok) throw new Error('예시 자료를 찾지 못했습니다.')
    const n = await importAll(await res.json())
    toast(`예시 자료 ${n}건을 불러왔습니다.`)
    await refresh()
  } catch (e) {
    error.value = e.message
  }
}

async function create() {
  error.value = ''
  const name = alias.value.trim() || autoName()
  try {
    if (mentees.value.some((m) => m.alias === name)) throw new Error('같은 별칭의 멘티가 이미 있습니다.')
    await saveItem({ alias: name, formId: PROFILE_FORM, title: '멘티 정보', draft: emptyProfile() })
    router.push(menteePath(name))
  } catch (e) {
    error.value = e.message
  }
}
</script>

<template>
  <div class="shell">
    <h1>내 멘티</h1>
    <p class="muted">멘티마다 종합계획서, 회차별 활동보고서, 완료보고서를 한곳에서 작성합니다. 자료는 이 브라우저에만 저장되고 서버로 보내지 않습니다.</p>

    <router-link v-for="m in mentees" :key="m.alias" :to="menteePath(m.alias)" class="card mentee-card" data-test="mentee-card">
      <div class="row">
        <strong style="font-size: 1.05rem">{{ m.alias }}</strong>
        <span v-if="m.profile?.subject" class="tag">{{ m.profile.subject }}</span>
        <span v-if="m.profile?.mode" class="tag">{{ m.profile.mode }}</span>
        <span style="flex: 1"></span>
        <span class="muted">활동보고서 {{ m.status.reports }}건</span>
      </div>
      <div class="muted" style="margin-top: 4px">{{ m.next }}</div>
    </router-link>
    <p v-if="!mentees.length" class="card muted">아직 등록한 멘티가 없습니다. 아래에서 추가하거나 예시 멘티를 불러와 써 보세요.</p>

    <h2>멘티 추가</h2>
    <form class="card" @submit.prevent="create">
      <label class="field"><span class="name">구분할 이름 (선택)</span>
        <input v-model="alias" placeholder="비워 두면 '멘티 1'처럼 자동으로 붙습니다" maxlength="30" data-test="new-alias" />
        <span class="notice">멘티가 여럿일 때 서로 구분하려는 이름입니다. 과목처럼 본인만 알아볼 수 있게 적고, 실명은 쓰지 마세요.</span>
      </label>
      <div v-if="error" class="box error">{{ error }}</div>
      <button class="primary">멘티 추가</button>
    </form>

    <div class="card">
      <strong>먼저 써 보고 싶다면</strong>
      <p class="muted">지어낸 멘티 4명의 자료를 불러옵니다: 16회차를 마친 멘티, 멘토 교체를 앞둔 멘티, 막 매칭된 멘티, 결석이 있었던 멘티. 실제 인물이 아니며 이 브라우저에만 저장됩니다.</p>
      <button type="button" data-test="load-samples" @click="loadSamples">예시 멘티 불러오기</button>
    </div>
  </div>
</template>
