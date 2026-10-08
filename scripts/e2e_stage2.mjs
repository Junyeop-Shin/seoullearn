// 2단계 화면을 실제 브라우저(헤드리스 크롬)로 눌러 보는 점검 스크립트.
// 완료보고서(붙여넣기 → 초안) → 인계 요약 → 종합계획서에서 인계 요약 불러오기 → 이음단 요청 → 관리자: 답 못 한 질문
//
//   ADMIN_USERNAME=e2e_admin ADMIN_PASSWORD=e2e-admin-pass-1 docker compose up -d backend frontend ai-server
//   node scripts/e2e_stage2.mjs <스크린샷 저장 폴더>      (playwright 설치는 e2e_demo.mjs 참고)
//
// 실제 LLM을 10번 안팎 호출한다. 가상 데이터(synthetic/)만 쓴다. 끝나면 만든 계정(e2e_*)과 저장된 질문은 DB에서 직접 지운다.
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { createRequire } from 'node:module'
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
const ctx = await browser.newContext({ viewport: { width: 1100, height: 900 }, permissions: ['clipboard-read', 'clipboard-write'], acceptDownloads: true })
const page = await ctx.newPage()
page.on('dialog', (d) => d.accept())
const errors = []
page.on('pageerror', (e) => errors.push(String(e)))
const idle = () => page.waitForFunction(() => !/만드는 중입니다/.test(document.body.innerText), null, { timeout: 120000 })

await page.goto(base + '/login')
await page.getByRole('button', { name: '멘토 계정 만들기' }).click()
await page.locator('input[autocomplete=username]').fill(user)
await page.locator('input[type=password]').fill('e2e-pass-1234')
await page.getByRole('button', { name: '가입하고 시작하기' }).click()
await page.waitForURL(base + '/')
log('로그인: OK', user, '| 관리자 메뉴 보임:', await page.getByRole('link', { name: '답 못 한 질문' }).count())

// 답 없는 질문 하나 (관리자 목록에 모이는지 보려고)
await page.locator('textarea').fill('가람중 멘티 활동인증서를 영문으로도 받을 수 있나요?')
await page.getByRole('button', { name: '질문하기' }).click()
await page.waitForSelector('[data-test=route]', { timeout: 120000 })

// 완료보고서
await page.goto(base + '/completion')
await page.waitForSelector('[data-key=extension_mentor]')
await page.locator('input[list=alias-list]').fill('수학 고2 A')
await page.locator('summary').click()
await page.locator('details textarea').fill(pasted('M1', '수학'))
await page.getByRole('button', { name: '회차별로 나누기' }).click()
await page.waitForSelector('text=16건을 읽었습니다')
await page.locator('form textarea').first().fill('시발점 수1 완강\n기말고사 수학 3등급\n오답노트 습관')
await page.locator('[data-key=extension_mentor]').selectOption({ index: 1 })
await page.locator('[data-key=extension_mentee]').selectOption({ index: 1 })
await page.getByRole('button', { name: '완료보고서 초안 만들기' }).click()
await page.waitForSelector('[data-draft=session_list]', { timeout: 120000 })
const list = (await page.locator('[data-draft=session_list]').inputValue()).split('\n')
const draftText = (await page.locator('[data-draft]').evaluateAll((els) => els.map((e) => e.value).join('\n')))
log('완료보고서 수행리스트:', list.length, '줄 |', list[0])
log('  감성케어 칸:', JSON.stringify(await page.locator('[data-draft=emotional_care]').inputValue()), '| 성취도 줄 수:', (await page.locator('[data-draft=achievement]').inputValue()).split('\n').length)
log('  초안에 이름·전화·정서:', /김민지|010-0000|부모님|다퉈/.test(draftText), '| 경고:', (await page.locator('[data-test=warnings]').innerText()).replace(/\n/g, ' ').slice(0, 90))
await page.getByRole('button', { name: '보관함에 저장' }).click()
await page.waitForSelector('text=보관함에 저장했습니다')
await page.screenshot({ path: `${out}/5-completion.png`, fullPage: true })

// 인계 요약
await page.goto(base + '/handover')
await page.locator('input[list=alias-list]').fill('영어 중2 B')
await page.locator('summary').click()
await page.locator('details textarea').fill(pasted('M2', '영어'))
await page.getByRole('button', { name: '회차별로 나누기' }).click()
await page.waitForSelector('text=8건을 읽었습니다')
await page.getByRole('button', { name: '인계 요약 만들기' }).click()
await page.waitForSelector('[data-summary=attitude]', { timeout: 120000 })
const keys = await page.locator('[data-summary]').evaluateAll((els) => els.map((e) => [e.dataset.summary, e.value]))
for (const [k, v] of keys) log('  인계', k + ':', v.slice(0, 110))
log('  금지 표현:', /가람중|중간고사|성적|서운|군입대|어려워/.test(keys.map((k) => k[1]).join(' ')))
await page.getByRole('button', { name: '보관함에 저장' }).click()
await page.waitForSelector('text=보관함에 저장했습니다')
await page.screenshot({ path: `${out}/6-handover.png`, fullPage: true })

// 종합계획서에서 인계 요약 불러오기
await page.goto(base + '/plan')
await page.waitForSelector('[data-key=duration]')
await page.locator('input[list=alias-list]').fill('영어 중2 B')
await page.waitForSelector('text=인계 요약도 불러왔습니다')
await page.locator('summary').click()
log('종합계획서 인계 칸에 채워짐:', (await page.locator('details textarea').first().inputValue()).slice(0, 40))

// 이음단 요청
await page.goto(base + '/ieumdan')
await page.locator('select').selectOption('일정 변경')
const soon = new Date(Date.now() + 86400000), later = new Date(Date.now() + 5 * 86400000)
const dt = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}T19:00`
await page.locator('input[type=datetime-local]').nth(0).fill(dt(soon))
await page.locator('input[type=datetime-local]').nth(1).fill(dt(later))
await page.getByRole('button', { name: '요청 메시지 만들기' }).click()
await page.waitForSelector('[data-test=message]')
log('이음단 요청:', (await page.locator('[data-test=message]').innerText()).replace(/\n/g, ' | ').slice(0, 120))
log('  3일 전 경고:', /3일 전/.test(await page.locator('[data-test=warnings]').innerText()))

// 관리자
await page.goto(base + '/admin/unanswered')
await page.waitForURL(base + '/')
log('멘토가 관리자 화면에 가면: 첫 화면으로 돌려보냄')
await page.getByRole('button', { name: '로그아웃' }).click()
await page.waitForURL('**/login')
await page.locator('input[autocomplete=username]').fill('e2e_admin')
await page.locator('input[type=password]').fill('e2e-admin-pass-1')
await page.getByRole('button', { name: '로그인' }).click()
await page.waitForURL(base + '/')
await page.getByRole('link', { name: '답 못 한 질문' }).click()
await page.waitForSelector('table tr >> nth=1')
const rows = await page.locator('table tr').allInnerTexts()
log('관리자 목록:', rows.length - 1, '건 |', rows[1].replace(/\t/g, ' | ').slice(0, 110))
log('  학교명 가려짐:', rows.join(' ').includes('[학교명]'), '| 원문 학교명 노출:', rows.join(' ').includes('가람중'))
const [dl] = await Promise.all([page.waitForEvent('download'), page.getByRole('button', { name: 'CSV로 내보내기' }).click()])
await dl.saveAs(`${out}/unanswered.csv`)
log('  CSV 첫 줄:', readFileSync(`${out}/unanswered.csv`, 'utf-8').split('\r\n')[0].replace('﻿', '(BOM)'))
const n = rows.length - 1
await page.getByRole('button', { name: '삭제' }).first().click()
await page.waitForFunction((k) => document.querySelectorAll('table tr').length - 1 < k || !document.querySelector('table'), n)
log('  삭제 후:', Math.max(0, (await page.locator('table tr').count()) - 1), '건')
await page.screenshot({ path: `${out}/7-admin.png`, fullPage: true })
log('브라우저 오류:', errors.length ? errors : '없음')
await browser.close()
