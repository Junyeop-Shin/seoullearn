import { reactive } from 'vue'
import { api } from '../api/client'
import { clearChat } from './chat'

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

/** 회원 탈퇴: 서버의 계정을 지운다. 이 브라우저의 멘티 자료는 계정과 별개라 남는다. */
export async function withdraw() {
  await api.withdraw()
  auth.user = null
  clearChat()
}

/** 서버가 로그아웃을 받아들였을 때만 화면도 로그아웃한다 (실패했는데 화면만 바뀌면 새로 고침 한 번에 다시 로그인된다). */
export async function logout() {
  await api.logout()
  auth.user = null
  clearChat()
}
