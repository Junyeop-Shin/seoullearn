// 화면을 실제 브라우저(헤드리스 크롬)로 끝까지 눌러 보는 점검 스크립트.
// 로그인 → 설정 → 매뉴얼 질문 → 내 멘티(추가, 기본 정보) → 사전 연락 문자 → 종합계획서① → 활동보고서(작성, 다시 열기)
// → 두 번째 멘티: 붙여 넣은 보고서로 완료보고서·인계 요약 → 멘티 자료 내보내기 → 회기 정리 → 백업·복원
//
//   docker compose up -d frontend ai-server
//   (임시 폴더에서) npm install --no-save playwright && npx playwright install chromium
//   (그 폴더에서) node <저장소>/scripts/e2e_demo.mjs <스크린샷 저장 폴더>
//
// 실제 LLM을 15번 안팎 호출한다. 가상 데이터(synthetic/)만 쓴다. 끝나면 만든 계정(e2e_*)은 DB에서 직접 지운다.
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
const { chromium } = createRequire(resolve(process.cwd(), 'x.js'))('playwright')

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const load = (p) => JSON.parse(readFileSync(resolve(root, p), 'utf-8'))
const fields = load('forms/activity_report.json').fields
const pasted = (name, subject) => load(`synthetic/sessions_${name}.json`).sessions.map((s) => {
  const r = { session_date: s.date, session_no: s.session_no, subject, course: '가상 강좌', ...s.mentor_input, session_content: s.mentor_input.notes }
  return fields.map((f) => `${f.label}: ${({ mentee_name: '김민지', mentee_grade: '고2', mentor: '홍길동' })[f.key] ?? r[f.key] ?? ''}`).join('\n')
}).join('\n\n')

const base = 'http://localhost:3000'
const out = process.argv[2] || '.'
const user = 'e2e_' + Math.random().toString(36).slice(2, 8)
const log = (...a) => console.log(...a)
const browser = await chromium.launch()
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, permissions: ['clipboard-read', 'clipboard-write'], acceptDownloads: true })
const page = await ctx.newPage()
page.on('dialog', (d) => d.accept())
const errors = []
page.on('pageerror', (e) => errors.push(String(e)))
const shot = (n) => page.screenshot({ path: `${out}/${n}.png`, fullPage: true })
const key = (k) => page.locator(`[data-key=${k}]`)
const mentee = (alias, rest = '') => `${base}/mentees/${encodeURIComponent(alias)}${rest}`

// 로그인과 설정
await page.goto(base + '/mentees')
await page.waitForURL('**/login')
await page.getByRole('button', { name: '멘토 계정 만들기' }).click()
await page.locator('input[autocomplete=username]').fill(user)
await page.locator('input[type=password]').fill('e2e-pass-1234')
await page.getByRole('button', { name: '가입하고 시작하기' }).click()
await page.waitForURL(base + '/')
await page.goto(base + '/settings')
await page.locator('input').fill('https://open.kakao.com/o/sample123'); await page.getByRole('button', { name: '저장' }).click()
log('로그인·설정: OK', user)

// 매뉴얼 질문 3개
await page.goto(base + '/')
const ask = async (q) => {
  const n = await page.locator('.bubble.bot').count()
  await page.locator('textarea').fill(q); await page.getByRole('button', { name: '질문하기' }).click()
  await page.waitForFunction((k) => document.querySelectorAll('.bubble.bot').length > k && !document.body.innerText.includes('답변을 찾는 중'), n, { timeout: 90000 })
  const b = page.locator('.bubble.bot').last()
  return `근거 ${await b.locator('[data-test=citations] .mini').count()} · 오픈채팅 버튼 ${await b.locator('[data-test=route] a').count()} · 문의 초안 ${await b.locator('[data-test=inquiry]').count()} · 가림 ${await b.locator('[data-test=pii]').count()}`
}
log('질문(답 있음):', await ask('가람중 멘티가 20분 늦게 들어왔는데 어떻게 처리하나요?'))
log('질문(답 없음):', await ask('활동인증서를 영문으로도 발급받을 수 있나요?'))
log('질문(이음단):', await ask('오프라인 멘토링 일정을 바꾸려면 누구한테 말해야 하나요?'))

// 내 멘티: 추가와 기본 정보
const A = '국어 고1 C'
await page.goto(base + '/mentees')
await page.locator('[data-test=new-alias]').fill(A); await page.getByRole('button', { name: '멘티 추가' }).click()
await page.waitForURL(mentee(A))
log('멘티 추가 직후 안내:', await page.locator('[data-test=next-step]').innerText())
for (const [k, v] of Object.entries({ subject: '국어', course: '(가상) 고1 국어 문학 개념', goal: '문학 감 잡기, 인강 끝까지 듣기', level: '모의고사 국어 3~4등급, 문학이 약함' })) await page.locator(`[data-profile=${k}]`).fill(v)
await page.locator('[data-profile=mode]').selectOption('온라인'); await page.locator('[data-profile=duration]').selectOption('60'); await page.locator('[data-profile=weekday]').selectOption('월')
await page.locator('[data-profile=start_datetime]').fill('2026-10-12T20:00')
await page.getByRole('button', { name: '기본 정보 저장' }).click()
await page.waitForSelector('[data-test=profile-view]')
log('기본 정보 저장 후 안내:', await page.locator('[data-test=next-step]').innerText())

// 사전 연락 문자
await page.getByText('사전 연락 문자').first().click(); await page.waitForURL('**/pre-contact**')
await page.getByRole('button', { name: '문자 초안 만들기' }).click(); await page.waitForSelector('[data-test=sms]')
const sms = await page.locator('[data-test=sms]').innerText()
log('사전 연락 문자:', sms.length, '자 | 끝:', sms.slice(-30))

// 종합계획서①
await page.goto(mentee(A, '/plan')); await page.waitForSelector('text=기본 정보에서 일정과 목표를 불러왔습니다')
log('종합계획서 자동 입력:', await key('weekday').inputValue(), await key('start_datetime').inputValue(), '|', await key('subject_time').inputValue())
await page.locator('textarea').first().fill(load('synthetic/courses.json').courses.find((c) => c.id === 'C3').units.map((u) => u.title).join('\n'))
await page.getByRole('button', { name: '강 목록으로 정리' }).click(); await page.waitForSelector('text=24강을 읽었습니다')
await page.locator('[data-test=save-course] input').fill('(가상) 고1 국어 문학 개념'); await page.getByRole('button', { name: '내 강좌로 저장' }).click()
await page.waitForSelector('text=내 강좌에 저장했습니다')
await page.getByRole('button', { name: '16회차 계획 만들기' }).click(); await page.waitForSelector('table tr >> nth=16', { timeout: 90000 })
await page.getByRole('button', { name: '종합계획서① 초안 만들기' }).click(); await page.waitForSelector('[data-draft=learning_goal]', { timeout: 90000 })
log('종합계획서① 학습목표:', await page.locator('[data-draft=learning_goal]').inputValue())
log('  커리큘럼 줄 수:', (await page.locator('[data-draft=curriculum]').inputValue()).split('\n').length)
await page.locator('[data-copy=learning_goal]').click()
await page.getByRole('button', { name: '보관함에 저장' }).first().click(); await page.waitForSelector('text=보관함에 저장했습니다')
await shot('1-plan')

// 활동보고서 1회차: 작성 → 저장 → 다시 열기
await page.goto(mentee(A)); await page.waitForSelector('[data-test=sessions]')
log('계획서 저장 후 안내:', await page.locator('[data-test=next-step]').innerText())
await page.locator('[data-session="1"]').click(); await page.waitForSelector('[data-test=autofill]')
log('활동보고서 자동 입력:', await key('session_no').inputValue(), '회차 |', await key('session_date').inputValue(), '|', await key('subject').inputValue(), '|', await key('course').inputValue())
for (const [k, v] of Object.entries({ actual_time: '20:01~21:02', scope: '1강 문학 감상의 관점', goal: '감상의 관점 구분하기', attendance: '정시', lecture_progress: '1강 수강', homework: '첫 회차라 없음',
  session_content: '감상의 관점 네 가지 설명. 김민지 학생 어머님이 010-0000-0000로 상담 원하심. 마지막에 부모님이랑 다퉈서 속상하다고 해서 얘기 들어줌' })) await key(k).fill(v)
await key('progress_scale').selectOption('잘함'); await key('understanding_scale').selectOption('보통')
await page.getByRole('button', { name: '초안 만들기' }).click(); await page.waitForSelector('[data-draft=session_content]', { timeout: 90000 })
const content = await page.locator('[data-draft=session_content]').inputValue()
log('  학습 내용 초안:', content, '| 이름·전화·정서 노출:', /김민지|010-0000|다퉈|부모님/.test(content))
log('  가린 정보:', await page.locator('[data-test=pii]').innerText(), '| 안내 수:', await page.locator('[data-test=reminders] li').count())
await page.locator('[data-draft=session_content]').fill(content + ' (멘토 수정)')
await page.getByRole('button', { name: '저장', exact: true }).click(); await page.waitForSelector('text=저장했습니다')
await page.goto(mentee(A)); await page.waitForSelector('[data-session="1"].done')
log('회차 목록: 저장한 회차', await page.locator('.session.done').count(), '| 안내:', await page.locator('[data-test=next-step]').innerText())
await shot('2-mentee')
await page.locator('[data-session="1"]').click(); await page.waitForSelector('[data-test=reopened]')
log('다시 열기: 고친 글 유지 =', (await page.locator('[data-draft=session_content]').inputValue()).endsWith('(멘토 수정)'))

// 두 번째 멘티: 붙여 넣은 보고서로 완료보고서와 인계 요약
const B = '영어 중2 B'
await page.goto(base + '/mentees'); await page.locator('[data-test=new-alias]').fill(B); await page.getByRole('button', { name: '멘티 추가' }).click()
await page.waitForURL(mentee(B))
await page.goto(mentee(B, '/handover')); await page.waitForSelector('[data-test=status]')
await page.locator('summary').click(); await page.locator('details textarea').fill(pasted('M2', '영어'))
await page.getByRole('button', { name: '회차별로 나누기' }).click(); await page.waitForSelector('text=8건을 읽었습니다')
await page.getByRole('button', { name: '인계 요약 만들기' }).click(); await page.waitForSelector('[data-summary=attitude]', { timeout: 120000 })
const summary = await page.locator('[data-summary]').evaluateAll((els) => els.map((e) => e.value).join(' '))
log('인계 요약 항목:', await page.locator('[data-summary]').count(), '| 금지 표현:', /가람중|중간고사|성적|서운|군입대|어려워/.test(summary))
await page.getByRole('button', { name: '보관함에 저장' }).click(); await page.waitForSelector('text=보관함에 저장했습니다')
await page.goto(mentee(B, '/completion')); await page.waitForSelector('[data-key=extension_mentor]')
await page.locator('summary').click(); await page.locator('details textarea').fill(pasted('M1', '수학'))
await page.getByRole('button', { name: '회차별로 나누기' }).click(); await page.waitForSelector('text=16건을 읽었습니다')
await page.locator('form textarea').first().fill('수1 완강\n오답노트 습관')
await key('extension_mentor').selectOption({ index: 1 }); await key('extension_mentee').selectOption({ index: 1 })
await page.getByRole('button', { name: '완료보고서 초안 만들기' }).click(); await page.waitForSelector('[data-draft=session_list]', { timeout: 120000 })
log('완료보고서 수행리스트:', (await page.locator('[data-draft=session_list]').inputValue()).split('\n').length, '줄 | 감성케어 칸:', JSON.stringify(await page.locator('[data-draft=emotional_care]').inputValue()))
await page.getByRole('button', { name: '보관함에 저장' }).click(); await page.waitForSelector('text=보관함에 저장했습니다')

// 자료 관리: 내보내기 → 회기 정리 → 백업·복원
await page.goto(mentee(A)); await page.waitForSelector('[data-test=sessions]')
const [dl] = await Promise.all([page.waitForEvent('download'), page.getByRole('button', { name: '이 멘티 자료 내보내기' }).click()])
const file = `${out}/mentee.json`; await dl.saveAs(file)
log('멘티 자료 내보내기:', load(file).items.length, '건')
await page.getByRole('button', { name: '회기 정리' }).click(); await page.waitForSelector('text=건을 지웠습니다')
log('회기 정리 후: 저장한 회차', await page.locator('.session.done').count(), '| 기본 정보 유지:', await page.locator('[data-test=profile-view]').count())
await page.goto(base + '/vault'); await page.locator('input[type=file]').setInputFiles(file); await page.waitForSelector('text=건을 가져왔습니다')
await page.goto(mentee(A)); await page.waitForSelector('[data-session="1"].done')
log('백업 파일에서 가져온 뒤: 저장한 회차', await page.locator('.session.done').count())
await page.goto(base + '/mentees'); await page.waitForSelector('[data-test=mentee-card]')
log('멘티 목록:', (await page.locator('[data-test=mentee-card] strong').allInnerTexts()).join(', '))
await shot('3-mentees')
log('브라우저 오류:', errors.length ? errors : '없음')
await browser.close()
