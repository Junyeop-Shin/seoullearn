<script setup>
import { useRouter } from 'vue-router'
import { auth, logout } from './stores/auth'

const router = useRouter()
async function signOut() {
  await logout()
  router.replace('/login')
}
</script>

<template>
  <nav v-if="auth.user" class="top">
    <span class="brand">서울런 멘토 도우미</span>
    <router-link to="/">매뉴얼 질문</router-link>
    <router-link to="/pre-contact">사전 연락</router-link>
    <router-link to="/plan">종합계획서</router-link>
    <router-link to="/report">활동보고서</router-link>
    <router-link to="/completion">완료보고서</router-link>
    <router-link to="/handover">인계 요약</router-link>
    <router-link to="/ieumdan">이음단 요청</router-link>
    <router-link to="/places">협약 장소</router-link>
    <router-link to="/forms">기타 서식</router-link>
    <router-link to="/allowance">활동비 계산</router-link>
    <router-link to="/vault">보관함</router-link>
    <router-link to="/settings">설정</router-link>
    <router-link v-if="auth.user.role === 'ADMIN'" to="/admin/unanswered">답 못 한 질문</router-link>
    <span class="spacer"></span>
    <span class="muted">{{ auth.user.username }}</span>
    <button type="button" class="small" @click="signOut">로그아웃</button>
  </nav>
  <router-view />
</template>
