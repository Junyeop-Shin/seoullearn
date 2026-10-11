/** 초안 값 → 복사·편집용 글 (목록은 줄마다 하나). */
export function toText(value) {
  if (Array.isArray(value)) return value.join('\n')
  return value === null || value === undefined ? '' : String(value)
}

/** 초안 응답을 확인하고 그대로 돌려준다. 아동 안전 신호가 있으면 서버가 초안 없이 운영사무국 안내만 돌려준다: 그 안내를 오류로 던져 저장하지 않게 한다. */
export function checkDraft(res, fallback = '초안을 만들지 못했습니다. 잠시 후 다시 눌러 주세요.') {
  if (!Object.keys(res.draft).length) throw new Error(res.warnings[0] || fallback)
  if (res.error) throw new Error('AI의 답을 읽지 못했습니다. 잠시 후 다시 눌러 주세요.')   // 빈 칸으로 조용히 넘어가지 않는다
  return res
}
