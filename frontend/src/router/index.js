import { createRouter, createWebHistory } from 'vue-router'
import { auth, loadUser } from '../stores/auth'

const routes = [
  { path: '/login', component: () => import('../views/LoginView.vue'), meta: { public: true } },
  { path: '/', component: () => import('../views/ChatView.vue') },
  { path: '/report', component: () => import('../views/ReportView.vue') },
  { path: '/pre-contact', component: () => import('../views/PreContactView.vue') },
  { path: '/plan', component: () => import('../views/PlanView.vue') },
  { path: '/completion', component: () => import('../views/CompletionView.vue') },
  { path: '/handover', component: () => import('../views/HandoverView.vue') },
  { path: '/ieumdan', component: () => import('../views/IeumdanView.vue') },
  { path: '/admin/unanswered', component: () => import('../views/AdminUnansweredView.vue'), meta: { admin: true } },
  { path: '/vault', component: () => import('../views/VaultView.vue') },
  { path: '/settings', component: () => import('../views/SettingsView.vue') },
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
