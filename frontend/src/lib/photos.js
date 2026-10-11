// 오프라인 멘토링 인증사진: 사진 이름을 '멘티이름 N회기 N회차 월.일'로 바꿔 한 파일로 압축한다.
// 이 브라우저 안에서만 하고 사진은 저장하지도 서버로 보내지도 않는다.
import { zipSync } from 'fflate'

/** 묶음 이름: '홍길동 1회기 1회차 10.11' (date: 'YYYY-MM-DD') */
export function photoBase(name, term, round, date) {
  const [, m, d] = /^\d{4}-(\d{2})-(\d{2})/.exec(date || '') || []
  return [name, `${term || 1}회기`, `${round}회차`, m && `${Number(m)}.${Number(d)}`].filter(Boolean).join(' ')
}

/** 사진 이름: 첫 장은 묶음 이름 그대로, 다음부터 (1), (2)를 붙인다. 확장자는 원본 그대로 둔다. */
export function photoNames(base, files) {
  return files.map((f, i) => `${base}${i ? ` (${i})` : ''}${(/\.[A-Za-z0-9]+$/.exec(f.name || '') || ['.jpg'])[0].toLowerCase()}`)
}

/** 사진들(File 목록, 시작 → 중간 → 종료 순)을 이름을 바꿔 압축한 bytes. 사진은 이미 압축된 형식이라 다시 줄이지 않는다. */
export async function photoZip(base, files) {
  const names = photoNames(base, files)
  const entries = {}
  for (const [i, f] of files.entries()) entries[names[i]] = [new Uint8Array(await f.arrayBuffer()), { level: 0 }]
  return zipSync(entries)
}
