import { createRouter, createWebHistory } from 'vue-router'
import { auth, loadUser } from '../stores/auth'

const routes = [
  { path: '/login', component: () => import('../views/LoginView.vue'), meta: { public: true } },
  { path: '/', component: () => import('../views/ChatView.vue') },
  // 멘티별 작업 공간: 문서는 모두 멘티 아래에서 쓴다
  { path: '/mentees', component: () => import('../views/MenteesView.vue') },
  { path: '/mentees/new', component: () => import('../views/RegisterView.vue') },
  { path: '/mentees/:alias', component: () => import('../views/MenteeView.vue') },
  { path: '/mentees/:alias/manage', component: () => import('../views/ManageView.vue') },
  { path: '/mentees/:alias/report/:no?', component: () => import('../views/ReportView.vue') },
  { path: '/mentees/:alias/completion', component: () => import('../views/CompletionView.vue') },
  { path: '/mentees/:alias/handover', component: () => import('../views/HandoverView.vue') },
  // 멘티와 무관한 도구
  { path: '/schedule', component: () => import('../views/ScheduleView.vue') },
  { path: '/ieumdan', component: () => import('../views/ContactsView.vue') },   // 이음단 연락처 (자치구별 카카오톡 채널)
  { path: '/places', component: () => import('../views/PlacesView.vue') },
  { path: '/allowance', component: () => import('../views/AllowanceView.vue') },
  { path: '/bonding', component: () => import('../views/BondingView.vue') },       // 친화·성장활동 기록과 증빙사진
  { path: '/extension', component: () => import('../views/ExtensionView.vue') },   // 시간확대 신청 요건 확인
  { path: '/admin/unanswered', component: () => import('../views/AdminUnansweredView.vue'), meta: { admin: true } },
  { path: '/vault', component: () => import('../views/VaultView.vue') },
  { path: '/settings', component: () => import('../views/SettingsView.vue') },
  // 예전 주소(양식별 화면)는 멘티 목록으로 보낸다
  { path: '/pre-contact', redirect: '/mentees' },
  { path: '/mentees/:alias/plan', redirect: (to) => `/mentees/${encodeURIComponent(to.params.alias)}` },
  { path: '/report', redirect: '/mentees' },
  { path: '/plan', redirect: '/mentees' },
  { path: '/completion', redirect: '/mentees' },
  { path: '/handover', redirect: '/mentees' },
  { path: '/:rest(.*)*', redirect: '/' },
]

export const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach(async (to) => {
  if (!auth.checked) await loadUser()
  if (!to.meta.public && !auth.user) return '/login'
  if (to.path === '/login' && auth.user) return '/mentees'
  if (to.meta.admin && auth.user?.role !== 'ADMIN') return '/'
  return true
})
