// MVP 데모 시나리오를 실제 브라우저(헤드리스 크롬)로 끝까지 눌러 보는 점검 스크립트.
// 로그인 → 설정 → 매뉴얼 질문 3개 → 활동보고서 → 사전 연락 → 종합계획서①(신규·교체) → 보관함 내보내기·삭제·가져오기
//
//   docker compose up -d frontend ai-server
//   npm install --no-save playwright && npx playwright install chromium   (저장소 밖 임시 폴더에서 해도 된다)
//   node scripts/e2e_demo.mjs <스크린샷 저장 폴더>
//
// 실제 LLM을 10번 안팎 호출한다. 가상 문장만 쓴다. 끝나면 만든 계정(e2e_*)은 DB에서 직접 지운다.
import { chromium } from 'playwright'
const base = 'http://localhost:3000'
const user = 'e2e_' + Math.random().toString(36).slice(2, 8)
const log = (...a) => console.log(...a)
const browser = await chromium.launch()
const ctx = await browser.newContext({ viewport: { width: 1100, height: 900 }, permissions: ['clipboard-read', 'clipboard-write'] })
const page = await ctx.newPage()
page.on('dialog', (d) => { log('  [확인창]', d.message().slice(0, 60)); d.accept() })
const errors = []
page.on('pageerror', (e) => errors.push(String(e)))
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()) })
const shot = (n) => page.screenshot({ path: `${process.argv[2]}/${n}.png`, fullPage: true })

// 로그인
await page.goto(base + '/report')
await page.waitForURL('**/login')
await page.getByRole('button', { name: '멘토 계정 만들기' }).click()
await page.locator('input[autocomplete=username]').fill(user)
await page.locator('input[type=password]').fill('e2e-pass-1234')
await page.getByRole('button', { name: '가입하고 시작하기' }).click()
await page.waitForURL(base + '/')
log('로그인: OK', user)

// 설정: 오픈채팅 주소
await page.goto(base + '/settings')
await page.locator('input').fill('https://example.com/x'); await page.getByRole('button', { name: '저장' }).click()
log('설정 잘못된 주소:', await page.locator('form .row span').innerText())
await page.locator('input').fill('https://open.kakao.com/o/sample123'); await page.getByRole('button', { name: '저장' }).click()
log('설정 저장:', await page.locator('form .row span').innerText())

// 시나리오 1: 매뉴얼 질문 3개
await page.goto(base + '/')
const ask = async (q) => {
  const n = await page.locator('.bubble.bot').count()
  await page.locator('textarea').fill(q)
  await page.getByRole('button', { name: '질문하기' }).click()
  await page.waitForFunction((k) => document.querySelectorAll('.bubble.bot [data-test], .bubble.bot div').length && document.querySelectorAll('.bubble.bot').length > k && !document.body.innerText.includes('답변을 찾는 중'), n, { timeout: 90000 })
  const b = page.locator('.bubble.bot').last()
  return { text: (await b.innerText()).replace(/\n+/g, ' | ').slice(0, 230), cites: await b.locator('[data-test=citations] .mini').count(),
    link: await b.locator('[data-test=route] a').count(), inquiry: await b.locator('[data-test=inquiry]').count(), pii: await b.locator('[data-test=pii]').count() }
}
log('Q1 답 있음:', JSON.stringify(await ask('가람중 멘티가 20분 늦게 들어왔는데 어떻게 처리하나요?')))
log('Q2 답 없음:', JSON.stringify(await ask('활동인증서를 영문으로도 발급받을 수 있나요?')))
log('Q3 이음단:', JSON.stringify(await ask('오프라인 멘토링 일정을 바꾸려면 누구한테 말해야 하나요?')))
await shot('1-chat')

// 시나리오 2: 활동보고서
await page.goto(base + '/report')
await page.waitForSelector('[data-key=session_no]')
const fill = async (k, v) => { const el = page.locator(`[data-key=${k}]`); (await el.evaluate((e) => e.tagName)) === 'SELECT' ? await el.selectOption(v) : await el.fill(v) }
for (const [k, v] of Object.entries({ session_date: '2026-04-13', session_no: '6', subject: '수학', course: '수학의 시작, 시발점 - 수1', actual_time: '17:02~18:04',
  scope: 'T6 로그함수의 뜻과 그래프', goal: '로그함수와 지수함수의 역함수 관계 이해', progress_scale: '잘함', attendance: '정시', lecture_progress: 'T6 수강',
  homework: 'Step1 T5 완료', understanding_scale: '보통', session_content: '역함수 관계 그래프로 설명. 김민지 학생 어머님이 010-0000-0000로 시험범위 상담 원하심. 마지막에 부모님이랑 다퉈서 속상하다고 해서 얘기 들어줌' })) await fill(k, v)
await page.getByRole('button', { name: '초안 만들기' }).click()
await page.waitForSelector('[data-draft=session_content]', { timeout: 90000 })
const content = await page.locator('[data-draft=session_content]').inputValue()
log('활동보고서 학습 내용:', content)
log('  이름·전화·정서 노출:', /김민지|010-0000|다퉈|부모님/.test(await page.locator('body').innerText()) ? '있음(입력 칸 포함)' : '없음', '| 초안 칸에만:', /김민지|010-0000|다퉈|부모님/.test(content))
log('  멘티 성명 칸:', await page.locator('.card:has-text("멘티 성명") p').innerText(), '| 가린 정보:', await page.locator('[data-test=pii]').innerText())
log('  경고:', (await page.locator('[data-test=warnings]').innerText()).replace(/\n/g, ' '))
log('  안내 수:', await page.locator('[data-test=reminders] li').count())
await page.locator('[data-draft=session_content]').fill(content + ' (멘토 수정)')
await page.locator('[data-copy=session_content]').click()
log('  복사된 글 끝:', (await page.evaluate(() => navigator.clipboard.readText())).slice(-8))
await page.locator('input[list=alias-list]').fill('수학 고2 A')
await page.getByRole('button', { name: '보관함에 저장' }).click()
await page.waitForSelector('text=보관함에 저장했습니다')
await shot('2-report')

// 사전 연락 → 보관함
await page.goto(base + '/pre-contact')
await page.getByRole('button', { name: '질문지와 문자 초안 만들기' }).click()
await page.waitForSelector('text=통화에서 확인할 것')
log('사전 연락: 문자 조각', await page.locator('.mini .t').count(), '질문', await page.locator('label.field textarea').count())
const tas = page.locator('label.field textarea')
await tas.nth(0).fill('국어, 온라인 맞음'); await tas.nth(1).fill('월요일 저녁 8시 이후'); await tas.nth(2).fill('모의고사 국어 3~4등급, 문학이 약함'); await tas.nth(4).fill('문학 감 잡기, 인강 끝까지 듣기')
await page.locator('input[list=alias-list]').fill('국어 고1 C')
await page.getByRole('button', { name: '답변을 보관함에 저장' }).click()
await page.waitForSelector('text=보관함에 저장했습니다')

// 시나리오 3: 신규 멘티 종합계획서①
await page.goto(base + '/plan')
await page.waitForSelector('[data-key=duration]')
await page.locator('input[list=alias-list]').fill('국어 고1 C')
await page.getByRole('button', { name: '사전 연락 답변 불러오기' }).click()
await page.waitForSelector('text=불러왔습니다')
await page.locator('textarea').first().fill(Array.from({ length: 24 }, (_, i) => `${i + 1}강 문학 개념 ${i + 1}`).join('\n'))
await page.getByRole('button', { name: '강 목록으로 정리' }).click()
await page.waitForSelector('text=24강을 읽었습니다')
await page.locator('input[type=date]').first().fill('2026-10-12')
await page.getByRole('button', { name: '16회차 계획 만들기' }).click()
await page.waitForSelector('table tr >> nth=16', { timeout: 90000 })
log('주차별 계획 1회차:', await page.locator('table tr >> nth=1').innerText())
await fill('duration', '60'); await fill('weekday', '월'); await page.locator('[data-key=start_datetime]').fill('2026-10-12T20:00')
await page.getByRole('button', { name: '종합계획서① 초안 만들기' }).click()
await page.waitForSelector('[data-draft=learning_goal]', { timeout: 90000 })
log('종합계획서① 학습목표:', await page.locator('[data-draft=learning_goal]').inputValue())
log('  학생진단:', await page.locator('[data-draft=diagnosis]').inputValue())
log('  커리큘럼 줄 수:', (await page.locator('[data-draft=curriculum]').inputValue()).split('\n').length)
await page.locator('[data-copy=learning_goal]').click()
await shot('3-plan-new')

// 시나리오 4: 교체 멘티 (인계 요약 포함)
await page.locator('summary').click()
const ho = page.locator('details textarea')
await ho.nth(0).fill('8회 모두 정시 출석'); await ho.nth(1).fill('단어 과제는 들쭉날쭉함'); await ho.nth(3).fill('20강 중 8강까지 수강, 다음은 9강')
await page.getByRole('button', { name: '종합계획서① 초안 만들기' }).click()
await page.waitForFunction(() => !document.body.innerText.includes('초안을 만드는 중'), null, { timeout: 90000 })
await page.waitForTimeout(500)
log('교체 멘티 학생진단:', await page.locator('[data-draft=diagnosis]').first().inputValue())
await page.getByRole('button', { name: '보관함에 저장' }).first().click()
await page.waitForSelector('text=보관함에 저장했습니다')

// 보관함
await page.goto(base + '/vault')
await page.waitForSelector('.card strong')
log('보관함 별칭:', await page.locator('.card > strong').allInnerTexts(), '항목', await page.locator('table tr').count())
const [dl] = await Promise.all([page.waitForEvent('download'), page.getByRole('button', { name: '파일로 내보내기' }).click()])
const file = `${process.argv[2]}/vault.json`; await dl.saveAs(file)
await page.getByRole('button', { name: '보관함 전체 삭제' }).click()
await page.waitForSelector('text=저장된 초안이 없습니다')
await page.locator('input[type=file]').setInputFiles(file)
await page.waitForSelector('text=건을 가져왔습니다')
log('내보내기 → 전체 삭제 → 가져오기:', await page.locator('table tr').count(), '건 복원')
await shot('4-vault')
log('브라우저 오류:', errors.length ? errors : '없음')
console.log('USER=' + user)
await browser.close()
