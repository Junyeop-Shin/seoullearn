<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { PROFILE_FORM, docStatus, emptyProfile, menteePath, nextStep, profileFromVault } from '../lib/mentee'
import { COURSE_ALIAS } from '../lib/reports'
import { listAliases, listItems, saveItem } from '../stores/vault'

// 내 멘티: 멘티 목록. 멘티를 누르면 그 멘티의 작업 공간으로 간다.
const router = useRouter()
const mentees = ref([])
const alias = ref('')
const error = ref('')

onMounted(async () => {
  const out = []
  for (const a of (await listAliases()).filter((x) => x !== COURSE_ALIAS)) {
    const items = await listItems(a)
    const profile = profileFromVault(items)
    out.push({ alias: a, profile, status: docStatus(items), next: nextStep(items, profile) })
  }
  mentees.value = out
})

async function create() {
  error.value = ''
  const name = alias.value.trim()
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
    <p v-if="!mentees.length" class="card muted">아직 등록한 멘티가 없습니다. 아래에서 별칭을 정해 추가해 주세요.</p>

    <h2>멘티 추가</h2>
    <form class="card" @submit.prevent="create">
      <label class="field"><span class="name">멘티 별칭</span>
        <input v-model="alias" placeholder="예: 수학 고2 A" maxlength="30" required data-test="new-alias" />
        <span class="notice">실명을 쓰지 마세요. 과목처럼 본인만 알아볼 수 있는 이름을 씁니다. 이름, 학년, 학교, 연락처는 이 도구에 적지 않습니다.</span>
      </label>
      <div v-if="error" class="box error">{{ error }}</div>
      <button class="primary" :disabled="!alias.trim()">추가하고 시작하기</button>
    </form>
  </div>
</template>
