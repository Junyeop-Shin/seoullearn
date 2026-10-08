import { reactive } from 'vue'

// 화면 오른쪽 아래에 잠깐 뜨는 알림 (복사, 저장 결과).
export const toasts = reactive([])
let seq = 0

export function toast(message, ms = 2400) {
  const id = ++seq
  toasts.push({ id, message })
  setTimeout(() => {
    const i = toasts.findIndex((t) => t.id === id)
    if (i >= 0) toasts.splice(i, 1)
  }, ms)
}
