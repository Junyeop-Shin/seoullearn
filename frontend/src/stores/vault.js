// 브라우저 보관함 (IndexedDB). 멘토가 만든 초안을 멘티 별칭별로 이 브라우저 안에만 둔다. 서버로 보내지 않는다.
// 데이터 형식은 docs/vault_format.md 참고.
import { ref } from 'vue'

const DB_NAME = 'seoullearn-mentor-vault'
const STORE = 'items'
export const FORMAT = 'seoullearn-mentor-vault'
export const VERSION = 1
// 보관함 내용이 바뀔 때마다 1씩 오른다. 왼쪽 메뉴의 멘티 목록처럼 화면 밖에서 보관함을 따라가야 하는 곳에서 지켜본다.
export const vaultChanges = ref(0)

function open() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, 1)   // DB 구조의 버전. 파일 형식의 VERSION과 따로다 (올리면 onupgradeneeded를 함께 고친다)
    req.onupgradeneeded = () => {
      const store = req.result.createObjectStore(STORE, { keyPath: 'id' })
      store.createIndex('alias', 'alias')
    }
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

async function tx(mode, fn) {
  const db = await open()
  try {
    const out = await run(db, mode, fn)
    if (mode === 'readwrite') vaultChanges.value += 1
    return out
  } finally {
    db.close()
  }
}

function run(db, mode, fn) {
  return new Promise((resolve, reject) => {
    const t = db.transaction(STORE, mode)
    const out = fn(t.objectStore(STORE))
    t.oncomplete = () => resolve(out && 'result' in out ? out.result : out)
    t.onerror = () => reject(t.error)
    t.onabort = () => reject(t.error)
  })
}

function newId() {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`
}

/** 보관함 항목 하나를 저장한다. id가 있으면 덮어쓴다. */
export async function saveItem({ id, alias, formId, title, sessionNo = null, inputs = {}, extra = {}, draft = {} }) {
  const cleanAlias = String(alias || '').trim()
  if (!cleanAlias) throw new Error('멘티 별칭을 입력해 주세요.')
  if (!formId) throw new Error('양식이 지정되지 않았습니다.')
  // 저장 전에 일반 객체로 복사한다 (Vue 반응형 객체는 IndexedDB에 넣을 수 없다)
  const item = JSON.parse(
    JSON.stringify({
      id: id || newId(), alias: cleanAlias, formId, title: title || formId, sessionNo,
      savedAt: new Date().toISOString(), inputs, extra, draft,
    }),
  )
  await tx('readwrite', (s) => s.put(item))
  return item
}

export async function listItems(alias) {
  const all = await tx('readonly', (s) => s.getAll())
  const items = alias ? all.filter((x) => x.alias === alias) : all
  return items.sort((a, b) => (a.savedAt < b.savedAt ? 1 : -1))
}

export async function listAliases() {
  return [...new Set((await listItems()).map((x) => x.alias))].sort((a, b) => a.localeCompare(b, 'ko'))
}

export async function removeItem(id) {
  await tx('readwrite', (s) => s.delete(id))
}

export async function clearAll() {
  await tx('readwrite', (s) => s.clear())
}

/** 보관함 전체(alias를 주면 그 멘티만)를 파일로 내보낼 객체. 가져오기는 importAll로 한다. */
export async function exportAll(alias) {
  return { format: FORMAT, version: VERSION, exportedAt: new Date().toISOString(), items: await listItems(alias) }
}

/** 내보낸 파일 내용을 가져온다. 같은 id는 덮어쓴다. 가져온 개수를 돌려준다. */
export async function importAll(data) {
  if (!data || data.format !== FORMAT || !Array.isArray(data.items)) {
    throw new Error('보관함 파일이 아닙니다. 이 도구에서 내보낸 파일을 선택해 주세요.')
  }
  if (data.version > VERSION) throw new Error('더 새로운 버전에서 내보낸 파일입니다.')
  const valid = data.items.filter((x) => x && [x.id, x.alias, x.formId, x.savedAt].every((v) => typeof v === 'string'))
  await tx('readwrite', (s) => valid.forEach((x) => s.put(JSON.parse(JSON.stringify(x)))))
  return valid.length
}

/** 한 멘티의 자료를 지운다. keep에 적은 양식(formId)은 남긴다. 지운 개수를 돌려준다. */
export async function removeAlias(alias, keep = []) {
  const targets = (await listItems(alias)).filter((x) => !keep.includes(x.formId))
  await tx('readwrite', (s) => targets.forEach((x) => s.delete(x.id)))
  return targets.length
}

/** 내보낼 객체를 파일로 내려받는다. */
export function downloadJson(data, name) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }))
  const a = document.createElement('a')
  a.href = url
  a.download = name
  a.click()
  URL.revokeObjectURL(url)
}
