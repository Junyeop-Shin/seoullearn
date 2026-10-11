<script setup>
import { nextTick, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import ChecklistDialog from './components/ChecklistDialog.vue'
import NavIcon from './components/NavIcon.vue'
import { checklist } from './lib/checklist'
import { displayName, menteeFacts, menteePath, menteesFromVault } from './lib/mentee'
import { scheduleDue, todayText } from './lib/schedule'
import { stageBadge } from './lib/stage'
import { nameMask, release, restore } from './lib/nameMask'
import { toast, toasts } from './lib/toast'
import { auth, logout } from './stores/auth'
import { vaultChanges } from './stores/vault'

const router = useRouter()
const route = useRoute()
const open = ref(false)
const menuButton = ref(null)
watch(() => route.path, () => { open.value = false; checklist.items = null })   // 화면을 옮기면 메뉴와 체크리스트 팝업을 닫는다
// 휴대폰 메뉴: 열면 초점을 메뉴 안으로, 닫으면 [메뉴] 버튼으로 돌려놓는다
watch(open, async (v) => {
  await nextTick()
  ;(v ? document.querySelector('#side-menu a') : menuButton.value)?.focus?.()
})

// 멘티 한 명이 메뉴 하나다. 멘티 아래에는 단계와 무관한 도구만 둔다
const GROUPS = [
  { title: '도구', items: [{ to: '/', label: '매뉴얼 질문', icon: 'chat' }, { to: '/ieumdan', label: '이음단 연락처', icon: 'phone' },
    { to: '/places', label: '협약 장소', icon: 'pin' }, { to: '/allowance', label: '활동비 계산', icon: 'calc' },
    { to: '/bonding', label: '친화·성장활동', icon: 'folder' }, { to: '/extension', label: '시간확대 요건 확인', icon: 'calendar' }] },
  { title: '설정', items: [{ to: '/settings', label: '멘토 설정', icon: 'settings' }, { to: '/vault', label: '백업·복원', icon: 'archive' },
    { to: '/privacy', label: '개인정보 처리방침', icon: 'shield' }] },
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

const quoted = (list) => list.map((w) => `'${w}'`).join(', ')

async function signOut() {
  // 멘티 자료는 계정이 아니라 이 브라우저에 있다: 여럿이 쓰는 컴퓨터에 남기지 않게 알린다
  if (mentees.value.length && !window.confirm('로그아웃해도 멘티 자료는 이 브라우저에 남습니다. 여럿이 쓰는 컴퓨터라면 [취소]를 누르고 백업·복원에서 백업 파일을 내려받은 뒤 자료를 모두 지워 주세요. 로그아웃할까요?')) return
  try {
    await logout()
  } catch (e) {
    return toast(e.message)   // 서버가 로그아웃을 받지 못했으면 화면도 그대로 둔다
  }
  router.replace('/login')
}
</script>

<template>
  <div v-if="auth.user" class="app" @keydown.esc="open = false">
    <header class="topbar">
      <button ref="menuButton" type="button" :aria-expanded="open" aria-controls="side-menu" @click="open = !open">메뉴</button>
      <span>서울런 멘토 도우미</span>
    </header>
    <div v-if="open" class="scrim" @click="open = false"></div>
    <aside id="side-menu" class="side" :class="{ open }">
      <div class="brand"><span class="logo">런</span>서울런 멘토 도우미</div>
      <nav aria-label="주 메뉴">
        <router-link to="/mentees/new" class="nav add" data-test="nav-register"><NavIcon name="plus" />멘티 등록</router-link>
        <router-link to="/mentees" class="nav" data-test="nav-mentees"><NavIcon name="people" />내 멘티</router-link>
        <!-- 진행 중인 멘티만 보여 주고(종료한 멘티는 '내 멘티'에서 본다), 멘티가 많아도 아래 도구와 설정이 밀려나지 않게 목록만 따로 넘긴다 -->
        <div class="mentee-list">
          <router-link v-for="m in mentees.filter((x) => !x.profile.archived)" :key="m.alias" :to="menteePath(m.alias)" class="nav mentee" :class="{ 'router-link-exact-active': route.params.alias === m.alias }"
            :title="displayName(m.profile, m.alias)" data-test="nav-mentee">
            <span class="label"><strong>{{ m.profile.name || m.alias }}</strong><small v-if="menteeFacts(m.profile)">{{ menteeFacts(m.profile) }}</small></span><span class="badge">{{ stageBadge(m.profile) }}</span>
          </router-link>
        </div>
        <router-link to="/schedule" class="nav" data-test="nav-schedule"><NavIcon name="calendar" />오프라인 일정·장소<span v-if="due()" class="badge due" title="다음 달 일정을 이음단에 알릴 때입니다" data-test="schedule-due">알릴 때</span></router-link>
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
    <main class="main" :inert="open"><router-view :key="route.params.alias" /></main>
  </div>
  <router-view v-else />
  <ChecklistDialog />
  <!-- 보낼 때 이름으로 보고 가린 말. 이름이 아니면(예: 수학의 '지수') 멘토가 풀고 다시 보낸다 -->
  <div v-if="nameMask.words.length || nameMask.released.length" class="toasts mask" role="status" data-test="name-mask"><div class="toast">
    <template v-if="nameMask.released.length">
      {{ quoted(nameMask.released) }}은(는) 이제 가리지 않습니다. 다시 보내 주세요.
      <button type="button" class="small" data-test="name-mask-undo" @click="restore">되돌리기</button>
      <button type="button" class="small" @click="nameMask.released = []">닫기</button>
    </template>
    <template v-else>
      AI로 보내기 전에 이름으로 보고 가렸습니다: {{ quoted(nameMask.words) }}
      <button v-if="nameMask.loose.length" type="button" class="small" data-test="name-mask-off" @click="release">{{ quoted(nameMask.loose) }}은(는) 이름이 아닙니다</button>
      <button type="button" class="small" @click="nameMask.words = []">닫기</button>
    </template>
  </div></div>
  <div class="toasts" aria-live="polite"><div v-for="t in toasts" :key="t.id" class="toast">{{ t.message }}</div></div>
</template>
