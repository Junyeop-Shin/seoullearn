// 양식 스키마(GET /api/forms/{formId}) → 화면 입력 칸 목록.
// 멘토가 직접 넣는 칸(user, user_text)만 입력으로 그린다. 개인정보 칸과 AI·규칙이 채우는 칸은 그리지 않는다.

const CONTROL = { date: 'date', datetime: 'datetime-local', integer: 'number', enum: 'select', scale5: 'select', list: 'lines' }

export function inputFields(form) {
  const out = []
  for (const f of form.extra_inputs || []) out.push(toField(f, true))
  for (const f of form.fields || []) {
    if (f.pii || !['user', 'user_text'].includes(f.source)) continue
    out.push(toField(f, false))
  }
  return out
}

function toField(f, extra) {
  const control = CONTROL[f.type] || (f.source === 'user_text' ? 'textarea' : 'text')
  return {
    key: f.key, label: f.label, required: !!f.required, control, options: f.options || [],
    help: f.help || '', group: f.group || '', example: typeof f.example === 'string' ? f.example : '',
    min: f.rules?.min, max: f.rules?.max, default: f.default ?? '', extra,
  }
}

/** 결과 화면에 보여줄 칸 순서와 이름 (스키마의 모든 필드). */
export function draftFields(form) {
  return (form.fields || []).map((f) => ({ key: f.key, label: f.label, source: f.source, pii: !!f.pii, list: f.type === 'list' }))
}

export function emptyInputs(fields) {
  return Object.fromEntries(fields.map((f) => [f.key, f.default]))
}

/** 화면 값 → 서버로 보낼 값. 줄 단위 입력은 배열로, datetime-local은 '2026-10-12 20:00'으로. */
export function toPayload(fields, values) {
  const out = {}
  for (const f of fields) {
    let v = values[f.key]
    if (v === undefined || v === null) v = ''
    if (f.control === 'lines') v = String(v).split('\n').map((x) => x.trim()).filter(Boolean)
    else if (f.control === 'datetime-local') v = String(v).replace('T', ' ')
    else v = String(v).trim()
    out[f.key] = v
  }
  return out
}

/** 초안 값 → 복사·편집용 글. */
export function toText(value) {
  if (Array.isArray(value)) return value.join('\n')
  return value === null || value === undefined ? '' : String(value)
}
