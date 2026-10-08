<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api/client'
import { login } from '../stores/auth'

const router = useRouter()
const mode = ref('login')
const username = ref('')
const password = ref('')
const error = ref('')
const busy = ref(false)

async function submit() {
  error.value = ''
  busy.value = true
  try {
    if (mode.value === 'signup') await api.signup(username.value, password.value)
    await login(username.value, password.value)
    router.replace('/')
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="shell" style="max-width: 420px">
    <h1>서울런 멘토 도우미</h1>
    <form class="card" @submit.prevent="submit">
      <label class="field"><span class="name">아이디</span>
        <input v-model="username" autocomplete="username" required />
        <span v-if="mode === 'signup'" class="notice">영문 소문자, 숫자, 밑줄로 4~20자. 실명이나 학교명은 쓰지 마세요.</span>
      </label>
      <label class="field"><span class="name">비밀번호</span>
        <input v-model="password" type="password" :autocomplete="mode === 'signup' ? 'new-password' : 'current-password'" required />
        <span v-if="mode === 'signup'" class="notice">8자 이상</span>
      </label>
      <div v-if="error" class="box error">{{ error }}</div>
      <div class="row">
        <button class="primary" :disabled="busy">{{ mode === 'signup' ? '가입하고 시작하기' : '로그인' }}</button>
        <button type="button" @click="mode = mode === 'signup' ? 'login' : 'signup'">
          {{ mode === 'signup' ? '이미 계정이 있습니다' : '멘토 계정 만들기' }}
        </button>
      </div>
    </form>
    <p class="muted">이 도구는 멘티의 이름, 연락처, 학교를 입력받지 않습니다. 작성한 초안은 이 브라우저에만 보관됩니다.</p>
  </div>
</template>
