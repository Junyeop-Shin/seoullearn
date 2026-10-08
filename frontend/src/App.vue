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
    <router-link to="/vault">보관함</router-link>
    <router-link to="/settings">설정</router-link>
    <span class="spacer"></span>
    <span class="muted">{{ auth.user.username }}</span>
    <button type="button" class="small" @click="signOut">로그아웃</button>
  </nav>
  <router-view />
</template>
