import { toast } from './toast'

/** 클립보드에 복사하고 알림을 띄운다. 성공하면 true. */
export async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text)
    toast('복사했습니다.')
    return true
  } catch {
    toast('복사하지 못했습니다. 글을 직접 선택해 복사해 주세요.')
    return false
  }
}
