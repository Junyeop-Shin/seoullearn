import { reactive } from 'vue'
import { api } from '../api/client'

// 로그인 상태. 서버 세션이 기준이고, 여기에는 아이디와 역할만 둔다.
export const auth = reactive({ user: null, checked: false })

export async function loadUser() {
  try {
    auth.user = await api.me()
  } catch {
    auth.user = null
  }
  auth.checked = true
  return auth.user
}

export async function login(username, password) {
  auth.user = await api.login(username, password)
}

export async function logout() {
  try {
    await api.logout()
  } finally {
    auth.user = null
  }
}
