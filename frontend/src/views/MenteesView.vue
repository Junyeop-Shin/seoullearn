<script setup>
import { onMounted, ref } from 'vue'
import { menteeFacts, menteePath, menteesFromVault } from '../lib/mentee'
import { stageBadge } from '../lib/stage'
import { toast } from '../lib/toast'
import { loadSettings, saveSettings } from '../stores/settings'
import { importAll, removeAlias } from '../stores/vault'

// 내 멘티: 멘티 목록. 멘티를 누르면 그 멘티의 지금 단계 화면으로 간다.
const mentees = ref([])
const error = ref('')

async function refresh() {
  mentees.value = await menteesFromVault()
  error.value = ''
}
onMounted(refresh)

// 써 보기용 예시 자료 (가상 멘티 4명). 이 브라우저 보관함에만 들어간다
async function loadSamples() {
  try {
    const res = await fetch('/demo_vault.json')
    if (!res.ok) throw new Error('예시 자료를 찾지 못했습니다. 잠시 후 다시 눌러 주세요.')
    const n = await importAll(await res.json())
    toast(`예시 자료 ${n}건을 불러왔습니다.`)
    await refresh()
  } catch (e) {
    error.value = e.message
  }
}

// 단계별 연습용 멘티 (단계마다 바로 눌러 볼 수 있는 지점에 맞춰 둔 지어낸 멘티들. scripts/make_scenario_vault.py).
// 다시 누르면 그 멘티들을 처음 상태로 되돌린다. 멘토 설정이 비어 있으면 지어낸 이름과 연락처를 넣는다
async function loadScenario() {
  try {
    const res = await fetch('/scenario_vault.json')
    if (!res.ok) throw new Error('연습용 자료를 찾지 못했습니다. 잠시 후 다시 눌러 주세요.')
    const data = await res.json()
    if (!Array.isArray(data.items)) throw new Error('연습용 자료를 읽지 못했습니다. 잠시 후 다시 눌러 주세요.')
    const aliases = new Set(data.items.map((x) => x.alias))
    if (mentees.value.some((m) => aliases.has(m.alias)) && !window.confirm('연습용 멘티의 자료를 처음 상태로 되돌립니다. 고친 내용은 사라집니다. 되돌릴까요?')) return
    for (const alias of aliases) await removeAlias(alias)
    const n = await importAll(data)
    if (!loadSettings().name) saveSettings(data.mentor)
    toast(`연습용 멘티 자료 ${n}건을 불러왔습니다.`)
    await refresh()
  } catch (e) {
    error.value = e.message
  }
}
</script>

<template>
  <div class="shell">
    <h1>내 멘티</h1>
    <p class="muted">멘티를 고르면 지금 할 단계의 화면이 열립니다. 자료는 이 브라우저에만 저장됩니다.</p>

    <router-link v-for="m in mentees" :key="m.alias" :to="menteePath(m.alias)" class="card mentee-card" data-test="mentee-card">
      <div class="row">
        <span class="grow"><strong>{{ m.profile.name || m.alias }}</strong><small>{{ menteeFacts(m.profile) }}</small></span>
        <span class="tag">{{ m.profile.archived ? '종료한 멘티' : `${m.profile.term}회기 · ${stageBadge(m.profile)}` }}</span>
      </div>
    </router-link>
    <p v-if="!mentees.length" class="card muted">아직 등록한 멘티가 없습니다. 멘티를 등록하거나 예시 멘티를 불러와 써 보세요.</p>
    <div v-if="error" class="box error" role="alert">{{ error }}</div>
    <router-link to="/mentees/new" class="linkbutton primary" data-test="new-mentee">멘티 등록</router-link>

    <h2>먼저 써 보고 싶다면</h2>
    <div class="card">
      <p class="muted flush">지어낸 멘티 4명의 자료를 불러옵니다: 회기를 마친 멘티, 멘토 교체를 앞둔 멘티, 막 매칭된 멘티, 결석이 있었던 멘티. 실제 인물이 아니며 이 브라우저에만 저장됩니다.</p>
      <button type="button" class="gap-top" data-test="load-samples" @click="loadSamples">예시 멘티 불러오기</button>
      <p class="muted">사전 연락부터 완료보고서까지 단계마다 한 명씩 준비한 연습용 멘티를 불러옵니다. 다시 누르면 연습용 멘티의 자료를 처음 상태로 되돌립니다.</p>
      <button type="button" data-test="load-scenario" @click="loadScenario">단계별 연습용 멘티 불러오기</button>
    </div>
  </div>
</template>
