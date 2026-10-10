<script setup>
import { onMounted, ref } from 'vue'
import { displayName, menteePath, profileFromVault } from '../lib/mentee'
import { COURSE_ALIAS } from '../lib/reports'
import { stageBadge } from '../lib/stage'
import { toast } from '../lib/toast'
import { loadSettings, saveSettings } from '../stores/settings'
import { importAll, listAliases, listItems, removeAlias } from '../stores/vault'

// 내 멘티: 멘티 목록. 멘티를 누르면 그 멘티의 지금 단계 화면으로 간다.
const mentees = ref([])
const error = ref('')

async function refresh() {
  const out = []
  for (const a of (await listAliases()).filter((x) => x !== COURSE_ALIAS)) {
    const profile = profileFromVault(await listItems(a))
    if (profile) out.push({ alias: a, profile })
  }
  mentees.value = out
}
onMounted(refresh)

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

// AI 다듬기 확인용 멘티 (docs/ai_polish_check.md의 시나리오가 시작하는 지점에 맞춰 둔 지어낸 멘티 다섯 명).
// 다시 누르면 그 멘티들을 처음 상태로 되돌린다. 멘토 설정이 비어 있으면 지어낸 이름과 연락처를 넣는다
async function loadScenario() {
  try {
    const res = await fetch('/scenario_vault.json')
    if (!res.ok) throw new Error('확인용 자료를 찾지 못했습니다.')
    const data = await res.json()
    for (const alias of new Set(data.items.map((x) => x.alias))) await removeAlias(alias)
    const n = await importAll(data)
    if (!loadSettings().name) saveSettings(data.mentor)
    toast(`확인용 멘티 자료 ${n}건을 불러왔습니다.`)
    await refresh()
  } catch (e) {
    error.value = e.message
  }
}
</script>

<template>
  <div class="shell">
    <h1>내 멘티</h1>
    <p class="muted">멘티 한 명이 메뉴 하나입니다. 멘티를 고르면 사전 연락부터 완료보고서까지 지금 단계의 화면이 열립니다. 자료는 이 브라우저에만 저장됩니다.</p>

    <router-link v-for="m in mentees" :key="m.alias" :to="menteePath(m.alias)" class="card mentee-card" data-test="mentee-card">
      <div class="row">
        <strong style="font-size: 1.05rem">{{ displayName(m.profile, m.alias) }}</strong>
        <span style="flex: 1"></span>
        <span class="tag">{{ m.profile.term }}회기 · {{ stageBadge(m.profile) }}</span>
      </div>
    </router-link>
    <p v-if="!mentees.length" class="card muted">아직 등록한 멘티가 없습니다. 멘티를 등록하거나 예시 멘티를 불러와 써 보세요.</p>
    <div v-if="error" class="box error">{{ error }}</div>
    <router-link to="/mentees/new"><button type="button" class="primary" data-test="new-mentee">멘티 등록</button></router-link>

    <div class="card" style="margin-top: 24px">
      <strong>먼저 써 보고 싶다면</strong>
      <p class="muted">지어낸 멘티 4명의 자료를 불러옵니다: 회기를 마친 멘티, 멘토 교체를 앞둔 멘티, 막 매칭된 멘티, 결석이 있었던 멘티. 실제 인물이 아니며 이 브라우저에만 저장됩니다.</p>
      <button type="button" data-test="load-samples" @click="loadSamples">예시 멘티 불러오기</button>
      <p class="muted" style="margin-top: 14px">AI 다듬기를 직접 확인해 보려면 확인용 멘티 다섯 명을 불러옵니다(정가상, 한가상, 오가상, 이가상, 마가상). 확인 순서에 맞는 지점에 맞춰 두었고, 다시 누르면 처음 상태로 되돌립니다.</p>
      <button type="button" data-test="load-scenario" @click="loadScenario">확인용 멘티 불러오기</button>
    </div>
  </div>
</template>
