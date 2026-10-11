import { reactive } from 'vue'

// 화면 위쪽에 잠깐 뜨는 알림 (복사, 저장 결과).
export const toasts = reactive([])
let seq = 0

/** 긴 글은 읽을 시간을 더 준다 (한 글자에 0.09초쯤). */
export function toast(message, ms = 2400) {
  ms = Math.max(ms, String(message).length * 90)
  const id = ++seq
  toasts.push({ id, message })
  setTimeout(() => {
    const i = toasts.findIndex((t) => t.id === id)
    if (i >= 0) toasts.splice(i, 1)
  }, ms)
}
