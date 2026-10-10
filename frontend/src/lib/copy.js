import { toast } from './toast'

/** 클립보드에 복사하고 알림을 띄운다 (label이 있으면 '학습목표를 복사했습니다.'). 성공하면 true. */
export async function copyText(text, label = '') {
  try {
    await navigator.clipboard.writeText(text)
    const last = label.charCodeAt(label.length - 1) - 0xac00   // 받침이 있으면 '을'
    toast(label ? `${label}${last >= 0 && last % 28 ? '을' : '를'} 복사했습니다.` : '복사했습니다.')
    return true
  } catch {
    toast('복사하지 못했습니다. 글을 직접 선택해 복사해 주세요.')
    return false
  }
}
