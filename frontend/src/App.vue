<script setup>
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import NavIcon from './components/NavIcon.vue'
import { toasts } from './lib/toast'
import { auth, logout } from './stores/auth'

const router = useRouter()
const route = useRoute()
const open = ref(false)
watch(() => route.path, () => (open.value = false))

// 메뉴를 멘토링 흐름 순서로 묶는다
const GROUPS = [
  { title: '', items: [{ to: '/', label: '매뉴얼 질문', icon: 'chat' }, { to: '/mentees', label: '내 멘티', icon: 'people' }] },
  { title: '도구', items: [{ to: '/pre-contact', label: '사전 연락 문자', icon: 'phone' }, { to: '/ieumdan', label: '이음단 요청', icon: 'send' },
    { to: '/places', label: '협약 장소', icon: 'pin' }, { to: '/allowance', label: '활동비 계산', icon: 'calc' }, { to: '/forms', label: '기타 서식', icon: 'folder' }] },
  { title: '설정', items: [{ to: '/vault', label: '백업·복원', icon: 'archive' }, { to: '/settings', label: '설정', icon: 'settings' }] },
]

async function signOut() {
  await logout()
  router.replace('/login')
}
</script>

<template>
  <div v-if="auth.user" class="app">
    <header class="topbar">
      <button type="button" aria-label="메뉴 열기" @click="open = true">메뉴</button>
      <span>서울런 멘토 도우미</span>
    </header>
    <div v-if="open" class="scrim" @click="open = false"></div>
    <aside class="side" :class="{ open }">
      <div class="brand"><span class="logo">런</span>서울런 멘토 도우미</div>
      <nav aria-label="주 메뉴">
        <template v-for="g in GROUPS" :key="g.title">
          <div v-if="g.title" class="group">{{ g.title }}</div>
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
    <main class="main"><router-view /></main>
  </div>
  <router-view v-else />
  <div class="toasts" aria-live="polite"><div v-for="t in toasts" :key="t.id" class="toast">{{ t.message }}</div></div>
</template>
