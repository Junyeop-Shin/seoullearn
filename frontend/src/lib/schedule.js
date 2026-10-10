// 날짜 계산과 이름 채우기. 모두 이 브라우저 안에서 한다 (규칙만 쓰고 AI는 부르지 않는다).
export const WEEKDAYS = ['일', '월', '화', '수', '목', '금', '토']
const pad = (n) => String(n).padStart(2, '0')
const iso = (d) => `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())}`
const parse = (s) => {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(s || '')
  return m ? new Date(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3]))) : null
}

export function weekdayOf(dateText) {
  const d = parse(dateText)
  return d ? WEEKDAYS[d.getUTCDay()] : ''
}

/** 시작일부터 매주 같은 요일로 n번의 날짜. */
export function weeklyDates(startDate, n) {
  const d = parse(startDate)
  if (!d) return Array.from({ length: n }, () => '')
  return Array.from({ length: n }, (_, i) => iso(new Date(d.getTime() + i * 7 * 86400000)))
}

/** '17:00' + 60분 → '18:00'. */
export function endTime(start, minutes) {
  const m = /^(\d{1,2}):(\d{2})/.exec(start || '')
  if (!m) return ''
  const t = Number(m[1]) * 60 + Number(m[2]) + (Number(minutes) || 60)
  return `${pad(Math.floor(t / 60) % 24)}:${pad(t % 60)}`
}

/** 오늘(YYYY-MM-DD)이 든 달. */
export function thisMonth(today) {
  const d = parse(today)
  return { year: d.getUTCFullYear(), month: d.getUTCMonth() + 1 }
}

/** 오늘(YYYY-MM-DD) 기준 다음 달. */
export function nextMonth(today) {
  const { year, month } = thisMonth(today)
  return month === 12 ? { year: year + 1, month: 1 } : { year, month: month + 1 }
}

/** 정규 일정([{weekday, startTime}])으로 그 달의 날짜를 나열한다. [{date, start}] 날짜순. */
export function monthDates(regularSchedule, year, month) {
  const out = []
  const days = new Date(Date.UTC(year, month, 0)).getUTCDate()
  for (let day = 1; day <= days; day += 1) {
    const d = new Date(Date.UTC(year, month - 1, day))
    for (const r of regularSchedule || []) if (r.weekday === WEEKDAYS[d.getUTCDay()]) out.push({ date: iso(d), start: r.startTime || '' })
  }
  return out.sort((a, b) => (a.date + a.start < b.date + b.start ? -1 : 1))
}

/** 다음달 일정은 매월 20일쯤 이음단에 보낸다. 그 무렵(17~23일)인지. */
export function scheduleDue(today) {
  const d = parse(today)
  return !!d && d.getUTCDate() >= 17 && d.getUTCDate() <= 23
}

/** '10/5(월) 17:00~18:00' */
export function dateLine(row, minutes) {
  const d = parse(row.date)
  if (!d) return ''
  const time = row.start ? ` ${row.start}~${endTime(row.start, minutes)}` : ''
  return `${d.getUTCMonth() + 1}/${d.getUTCDate()}(${WEEKDAYS[d.getUTCDay()]})${time}`
}

/** 템플릿의 {자리}를 채운다. */
export function render(template, values) {
  return template.replace(/\{(\w+)\}/g, (_, k) => String(values[k] ?? '')).trim()
}

/** 이음단에 보낼 일정·장소 문구 한 건 (인사말 포함). 몇 년인지는 쓰지 않고 몇 월인지만 쓴다. rows: [{date, start}] */
export function monthlyText(template, { month, mentorName, menteeName, venue, rows, minutes }) {
  const dates = rows.filter((r) => r.date).map((r) => `- ${dateLine(r, minutes)}`).join('\n')
  return render(template, { month, mentorName: mentorName || '[멘토명]', menteeName: menteeName || '[멘티명]',
    venue: venue || '(미정) 가능한 장소 안내 부탁드립니다', dates: dates || '- (일정 확인 필요)' })
}

/** 서버가 만든 글의 자리표시를 이 브라우저에 있는 이름·연락처로 바꾼다. 값이 없으면 자리표시를 그대로 둔다. */
export function fillNames(text, { mentee = '', mentor = '', phone = '' } = {}) {
  let out = String(text ?? '')
  if (mentee) out = out.replaceAll('[멘티명]', mentee)
  if (mentor) out = out.replaceAll('[멘토명]', mentor)
  if (phone) out = out.replaceAll('[멘토 연락처]', phone)
  return out
}

export const todayText = () => {
  const d = new Date()
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}
