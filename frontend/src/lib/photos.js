// 오프라인 멘토링 인증사진: 사진 이름을 '멘티이름 N회기 N회차 월.일'로 바꿔 한 파일로 압축한다.
// 이 브라우저 안에서만 하고 사진은 저장하지도 서버로 보내지도 않는다.
import { zipSync } from 'fflate'

/** 묶음 이름: '홍길동 1회기 1회차 10.11' (date: 'YYYY-MM-DD') */
export function photoBase(name, term, round, date) {
  return [name, `${term || 1}회기`, `${round}회차`, monthDay(date)].filter(Boolean).join(' ')
}
/** 'YYYY-MM-DD' → '10.11' (없으면 빈 글) */
export function monthDay(date) {
  const [, m, d] = /^\d{4}-(\d{2})-(\d{2})/.exec(date || '') || []
  return m ? `${Number(m)}.${Number(d)}` : ''
}

const extOf = (f) => (/\.[A-Za-z0-9]+$/.exec(f.name || '') || ['.jpg'])[0].toLowerCase()

/** [[파일 이름(확장자 없이), File], …]을 그 이름으로 압축한 bytes. 확장자는 원본 그대로 둔다. 사진은 이미 압축된 형식이라 다시 줄이지 않는다. */
export async function namedZip(pairs) {
  const entries = {}
  for (const [name, f] of pairs) entries[`${name}${extOf(f)}`] = [new Uint8Array(await f.arrayBuffer()), { level: 0 }]
  return zipSync(entries)
}

/** 사진들(File 목록, 시작 → 중간 → 종료 순)을 이름을 바꿔 압축한 bytes. 첫 장은 묶음 이름 그대로, 다음부터 (1), (2)를 붙인다. */
export const photoZip = (base, files) => namedZip(files.map((f, i) => [`${base}${i ? ` (${i})` : ''}`, f]))

/** 압축한 bytes를 파일로 내려받는다. */
export function downloadZip(bytes, name) {
  const a = document.createElement('a')
  a.href = URL.createObjectURL(new Blob([bytes], { type: 'application/zip' }))
  a.download = `${name}.zip`
  a.click()
  setTimeout(() => URL.revokeObjectURL(a.href), 1000)   // 바로 지우면 내려받기가 취소되는 브라우저가 있다
  return a.download
}
