<script setup>
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import NavIcon from './components/NavIcon.vue'
import { displayName, menteeFacts, menteePath, menteesFromVault } from './lib/mentee'
import { scheduleDue, todayText } from './lib/schedule'
import { stageBadge } from './lib/stage'
import { toasts } from './lib/toast'
import { auth, logout } from './stores/auth'
import { vaultChanges } from './stores/vault'

const router = useRouter()
const route = useRoute()
const open = ref(false)
watch(() => route.path, () => (open.value = false))

// 멘티 한 명이 메뉴 하나다. 멘티 아래에는 단계와 무관한 도구만 둔다
const GROUPS = [
  { title: '도구', items: [{ to: '/', label: '매뉴얼 질문', icon: 'chat' }, { to: '/ieumdan', label: '이음단 연락처', icon: 'phone' },
    { to: '/places', label: '협약 장소', icon: 'pin' }, { to: '/allowance', label: '활동비 계산', icon: 'calc' }, { to: '/forms', label: '기타 서식', icon: 'folder' }] },
  { title: '설정', items: [{ to: '/settings', label: '멘토 설정', icon: 'settings' }, { to: '/vault', label: '백업·복원', icon: 'archive' }] },
]

// 보관함이 바뀌면 멘티 목록을 다시 읽는다
const mentees = ref([])
watch([() => auth.user, vaultChanges], async () => {
  try {
    mentees.value = auth.user ? await menteesFromVault() : []
  } catch {
    mentees.value = []
  }
}, { immediate: true })
// 매월 20일 전후에 진행 중인 오프라인 멘티가 있으면 '오프라인 일정·장소'에 표시를 붙인다 (다음달 일정을 이음단에 알릴 때)
const due = () => scheduleDue(todayText()) && mentees.value.some((m) => m.profile.mode === '오프라인' && !m.profile.archived)

async function signOut() {
  // 멘티 자료는 계정이 아니라 이 브라우저에 있다: 여럿이 쓰는 컴퓨터에 남기지 않게 알린다
  if (mentees.value.length && !window.confirm('멘티 자료는 로그아웃해도 이 브라우저에 남습니다. 여럿이 쓰는 컴퓨터라면 취소한 뒤 백업·복원에서 파일로 내보내고 보관함을 지워 주세요. 로그아웃할까요?')) return
  await logout()
  router.replace('/login')
}
</script>

<template>
  <div v-if="auth.user" class="app">
    <header class="topbar">
      <button type="button" :aria-expanded="open" aria-controls="side-menu" @click="open = !open">메뉴</button>
      <span>서울런 멘토 도우미</span>
    </header>
    <div v-if="open" class="scrim" @click="open = false"></div>
    <aside id="side-menu" class="side" :class="{ open }" @keydown.esc="open = false">
      <div class="brand"><span class="logo">런</span>서울런 멘토 도우미</div>
      <nav aria-label="주 메뉴">
        <router-link to="/mentees/new" class="nav add" data-test="nav-register"><NavIcon name="plus" />멘티 등록</router-link>
        <router-link to="/mentees" class="nav" data-test="nav-mentees"><NavIcon name="people" />내 멘티</router-link>
        <router-link v-for="m in mentees" :key="m.alias" :to="menteePath(m.alias)" class="nav mentee" :class="{ 'router-link-exact-active': route.params.alias === m.alias, archived: m.profile.archived }"
          :title="displayName(m.profile, m.alias)" data-test="nav-mentee">
          <span class="label"><strong>{{ m.profile.name || m.alias }}</strong><small v-if="menteeFacts(m.profile)">{{ menteeFacts(m.profile) }}</small></span><span class="badge">{{ stageBadge(m.profile) }}</span>
        </router-link>
        <router-link to="/schedule" class="nav" data-test="nav-schedule"><NavIcon name="calendar" />오프라인 일정·장소<span v-if="due()" class="dot" title="이번 달 20일 무렵입니다" data-test="schedule-due"></span></router-link>
        <template v-for="g in GROUPS" :key="g.title">
          <div class="group">{{ g.title }}</div>
          <router-link v-for="i in g.items" :key="i.to" :to="i.to" class="nav" :class="{ 'router-link-exact-active': i.to !== '/' && route.path.startsWith(i.to + '/') }"><NavIcon :name="i.icon" />{{ i.label }}</router-link>
        </template>
        <template v-if="auth.user.role === 'ADMIN'">
          <div class="group">관리자</div>
          <router-link to="/admin/unanswered" class="nav"><NavIcon name="shield" />답 못 한 질문</router-link>
        </template>
      </nav>
      <div class="foot">
        <div class="who">{{ auth.user.username }}<small>{{ auth.user.role === 'ADMIN' ? '관리자' : '멘토' }}</small></div>
        <button type="button" class="small" @click="signOut">로그아웃</button>
      </div>
    </aside>
    <main class="main"><router-view :key="route.params.alias" /></main>
  </div>
  <router-view v-else />
  <div class="toasts" aria-live="polite"><div v-for="t in toasts" :key="t.id" class="toast">{{ t.message }}</div></div>
</template>
