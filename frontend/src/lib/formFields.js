/** 초안 값 → 복사·편집용 글 (목록은 줄마다 하나). */
export function toText(value) {
  if (Array.isArray(value)) return value.join('\n')
  return value === null || value === undefined ? '' : String(value)
}
