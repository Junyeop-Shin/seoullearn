import { createApp } from 'vue'
import App from './App.vue'
import './assets/main.css'
import { toast } from './lib/toast'
import { router } from './router'

// 예전 판이 남긴 값(마지막으로 본 멘티 이름)을 지운다. 지금은 쓰지 않는다
try { localStorage.removeItem('seoullearn.currentMentee.v1') } catch { /* 저장소를 못 써도 지장 없다 */ }

const app = createApp(App)
// 화면 어디서든 처리하지 못한 오류(보관함 저장 실패 등)를 말없이 삼키지 않는다
app.config.errorHandler = (e) => {
  console.error(e)
  toast('처리하지 못했습니다. 화면을 새로 고친 뒤 다시 시도해 주세요.')
}
app.use(router).mount('#app')
