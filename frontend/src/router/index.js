import { createRouter, createWebHistory } from 'vue-router'
import { auth, loadUser } from '../stores/auth'

const routes = [
  { path: '/login', component: () => import('../views/LoginView.vue'), meta: { public: true } },
  { path: '/', component: () => import('../views/ChatView.vue') },
  // 멘티별 작업 공간: 문서는 모두 멘티 아래에서 쓴다
  { path: '/mentees', component: () => import('../views/MenteesView.vue') },
  { path: '/mentees/:alias', component: () => import('../views/MenteeView.vue') },
  { path: '/mentees/:alias/plan', component: () => import('../views/PlanView.vue') },
  { path: '/mentees/:alias/report/:no?', component: () => import('../views/ReportView.vue') },
  { path: '/mentees/:alias/completion', component: () => import('../views/CompletionView.vue') },
  { path: '/mentees/:alias/handover', component: () => import('../views/HandoverView.vue') },
  // 멘티와 무관한 도구
  { path: '/pre-contact', component: () => import('../views/PreContactView.vue') },
  { path: '/ieumdan', component: () => import('../views/IeumdanView.vue') },
  { path: '/places', component: () => import('../views/PlacesView.vue') },
  { path: '/allowance', component: () => import('../views/AllowanceView.vue') },
  { path: '/forms', component: () => import('../views/OtherFormsView.vue') },
  { path: '/forms/:formId', component: () => import('../views/OtherFormsView.vue') },
  { path: '/admin/unanswered', component: () => import('../views/AdminUnansweredView.vue'), meta: { admin: true } },
  { path: '/vault', component: () => import('../views/VaultView.vue') },
  { path: '/settings', component: () => import('../views/SettingsView.vue') },
  // 예전 주소(양식별 화면)는 멘티 목록으로 보낸다
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
  if (to.path === '/login' && auth.user) return '/'
  if (to.meta.admin && auth.user?.role !== 'ADMIN') return '/'
  return true
})
