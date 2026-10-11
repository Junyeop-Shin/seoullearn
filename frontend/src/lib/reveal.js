import { nextTick } from 'vue'

/** 방금 뜬 오류 상자를 보이는 자리로 끌어온다 (저장 버튼은 긴 양식의 맨 아래에, 오류 상자는 위에 있어 놓치기 쉽다). */
export const revealError = () => nextTick(() => document.querySelector('.box.error')?.scrollIntoView?.({ block: 'center', behavior: 'smooth' }))
