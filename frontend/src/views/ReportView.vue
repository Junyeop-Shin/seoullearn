<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '../api/client'
import MenteeHeader from '../components/MenteeHeader.vue'
import { copyText } from '../lib/copy'
import { menteePath, profileFromVault, regularSchedule, suggestDate } from '../lib/mentee'
import { changedLines, freshLines, mergeLines } from '../lib/plan'
import { absentText, applyLines, boxText, contentAuto, fromLines, halvesOf, joinLabel, progressLines, splitLabel, statusesOf, syncLines, toLines } from '../lib/report'
import { plannedRow, plannedWeek, previousHomework } from '../lib/reports'
import { endTime } from '../lib/schedule'
import { afterReport } from '../lib/stage'
import { toast } from '../lib/toast'
import { listItems, saveItem } from '../stores/vault'

// 한 회차 활동보고서. 화면은 플랫폼 입력 칸과 같은 구성이다: 이번 주차 학습 내용, 학습 진도, 학습 이해도, 기타, 건의사항 (항목마다 글상자 하나).
// 무엇을 쓰는지는 활동가이드 p.30을 따른다: 학습 내용 = 학습범위·학습목표, 학습 진도 = 출결·인강 수강·과제 수행, 학습 이해도 = 멘토링 학습 내용(내 준 과제 포함).
// 학습 내용은 종합계획서의 그 주차 계획에서, 학습 진도는 출석·인강·과제 선택에서 규칙으로 채운다. AI는 멘토가 대충 적은 글의 표현을 다듬을 때만 쓴다.
// 평가(매우 잘함 ~ 매우 노력필요)는 플랫폼에서 바로 고르므로 여기서는 받지 않는다.
const FORM_ID = 'activity_report'
defineOptions({ inheritAttrs: false })   // 멘티 화면이 모든 단계에 같은 값을 넘긴다: 안 쓰는 값이 화면 요소에 붙지 않게 한다
const props = defineProps({ embedded: { type: Boolean, default: false }, round: { type: Number, default: 0 } })
const emit = defineEmits(['saved'])
const route = useRoute()
const alias = String(route.params.alias)
const no = ref(props.round || Number(route.params.no) || 0)
const profile = ref(null)
const savedId = ref(undefined)
const loaded = ref(false)
const busy = ref('')
const error = ref('')
const notes = ref([])
const prevHw = ref(null)       // 지난 회차에 낸 인강·과제 {lecture, task, sentences}
const week = ref(null)         // 종합계획서의 이번 주차 계획 {row, course}
const next = ref('')           // 저장한 뒤 넘어갈 곳의 이름 (예: '2회차'). 저장 안내를 읽고 버튼으로 넘어간다

const q = reactive({ status: '출석', date: '', time: '', lectureDone: '', taskDone: '' })   // 멘토가 고른 것
// 플랫폼에 옮길 글. progress와 understanding은 시간확대(120분)면 전반·후반 두 칸
const sheet = reactive({ content: '', progress: [''], understanding: [''], etc: '', requests: '' })
const halves = computed(() => halvesOf(profile.value?.duration))
const absent = computed(() => !!absentText(q.status))   // 진행하지 못한 회차 (임박취소, 무단결석, 인정결석)
const polished = {}            // 마지막으로 AI가 다듬어 준 글. 그 뒤로 고치지 않은 줄은 다시 다듬지 않는다
const changes = ref(null)      // AI가 바꾼 내용 {items: [{label, before, after}], undo}
let planned = ''               // 종합계획서에서 가져온 학습 내용 (멘토가 고쳤는지 견주는 데 쓴다)
let auto = ['', '', '']        // 규칙으로 넣어 둔 학습 진도 줄 [출결, 인강, 과제]

// 무엇을 듣고 하기로 했는지: 따로 적어 둔 것이 있으면 그것을, 없으면 인강은 이번 주차 계획의 온라인 강의를 쓴다
const what = computed(() => ({ lecture: prevHw.value?.lecture || (week.value?.row.online || '').trim(), task: prevHw.value?.task || '' }))
function syncProgress() {
  const lines = progressLines({ status: q.status, time: q.time.trim(), lecture: q.lectureDone, task: q.taskDone, what: what.value })
  sheet.progress[0] = syncLines(sheet.progress[0], auto, lines)
  auto = lines
}
watch(() => [q.status, q.time, q.lectureDone, q.taskDone], () => { if (loaded.value && !absent.value) syncProgress() })
// 결석으로 바꾸면 학습 내용 칸을 결석 문구로, 되돌리면 계획에서 가져온 글로 바꾼다 (멘토가 고쳐 쓴 글은 건드리지 않는다)
watch(() => q.status, (now, before) => {
  if (!loaded.value) return
  const mine = sheet.content.trim()
  if (mine && mine !== planned.trim() && mine !== absentText(before)) return
  sheet.content = absentText(now) || planned
})

onMounted(async () => {
  try {
    const items = await listItems(alias)
    profile.value = profileFromVault(items)
    if (!no.value) no.value = profile.value?.currentRound || 1
    const blank = () => halves.value.map(() => '')
    Object.assign(sheet, { progress: blank(), understanding: blank() })
    prevHw.value = previousHomework(items, no.value, profile.value)
    week.value = plannedWeek(items, no.value)
    planned = contentAuto(week.value?.row, week.value?.course)
    const existing = items.filter((x) => x.formId === FORM_ID && Number(x.sessionNo ?? x.inputs?.session_no) === no.value)
      .sort((a, b) => (a.savedAt < b.savedAt ? 1 : -1))[0]
    if (existing) {
      // 저장한 보고서를 다시 연다
      savedId.value = existing.id
      const i = existing.inputs || {}, x = existing.extra || {}
      Object.assign(q, { status: i.status || '출석', date: i.session_date || '', time: i.actual_time || '' })
      if (x.sheet) {
        Object.assign(q, Object.fromEntries(Object.entries(x.quick || {}).filter(([k]) => k in q)))
        Object.assign(sheet, { content: x.sheet.content || '', etc: boxText(x.sheet.etc), requests: x.sheet.requests || '' })
        for (const key of ['progress', 'understanding']) sheet[key] = sheet[key].map((_, h) => boxText(x.sheet[key]?.[h]))
      } else {
        // 예전 화면으로 저장한 보고서: 저장된 글을 가까운 칸에 넣는다. 인강·과제 글에는 머리말을 붙여 다시 저장해도 완료보고서가 읽을 수 있게 한다
        const d = { ...i, ...existing.draft }
        const headed = (label, v) => (v && !String(v).startsWith(`${label}:`) ? `${label}: ${v}` : v)
        sheet.content = [d.scope && `학습범위: ${d.scope}`, d.goal && `학습목표: ${d.goal}`].filter(Boolean).join('\n')
        sheet.progress[0] = [headed('출결', d.attendance), headed('인강', d.lecture_progress), headed('과제', d.homework)].filter(Boolean).join('\n')
        sheet.understanding[0] = d.session_content || ''
        Object.assign(sheet, { etc: d.etc || '', requests: d.requests || '' })
        auto = progressLines({ status: q.status, time: q.time.trim() })   // 지금 값의 규칙 줄로 맞춰 둔다: 화면이 열리며 출결 줄을 하나 더 넣지 않게
      }
      auto = x.auto || auto
    } else {
      const p = profile.value || {}
      const when = plannedRow(items, no.value)   // 계획서에서 이 회차의 일시를 고쳐 두었으면 그것을 쓴다
      const start = when?.time || regularSchedule(p)[0]?.startTime
      Object.assign(q, { date: when?.date || suggestDate(p.start_datetime, no.value), time: start ? `${start}~${endTime(start, p.duration)}` : '' })
      sheet.content = planned
      syncProgress()
    }
  } catch (e) {
    error.value = e.message
  } finally {
    loaded.value = true
  }
})

const copy = (label, value) => copyText(value, label)

// 서버와 주고받는 글: 줄마다 줄 머리에 칸 이름표를 붙인다 (서버가 줄을 지키며 개인정보와 넣지 않는 내용을 거르고, 다듬을 때도 줄마다 다듬는다)
const tagged = () => ({
  attendance: toLines(sheet.progress.map((t, h) => [`p${h}`, t])),
  session_content: toLines(sheet.understanding.map((t, h) => [`u${h}`, t])),
  etc: toLines([['e', sheet.etc]]),
  requests: toLines([['r', sheet.requests]]),
})
function payload(texts) {
  const p = profile.value || {}
  return {
    status: q.status, session_date: q.date, session_no: String(no.value), actual_time: q.time,
    subject: p.subject === '기타' ? p.subjectEtc || '' : p.subject || '', course: p.course || '',   // 화면에는 없지만 완료보고서가 쓴다
    scope: absent.value ? '' : sheet.content,
    attendance: absent.value ? q.status : texts.attendance || q.status,
    session_content: absent.value ? '' : texts.session_content, etc: texts.etc, requests: texts.requests,
  }
}
// 서버가 돌려준 글을 칸에 다시 넣는다
function restore(texts) {
  const got = { ...fromLines(texts.attendance), ...fromLines(texts.session_content), ...fromLines(texts.etc), ...fromLines(texts.requests) }
  if (!absent.value) {
    sheet.progress = sheet.progress.map((t, h) => applyLines(t, got[`p${h}`]))
    sheet.understanding = sheet.understanding.map((t, h) => applyLines(t, got[`u${h}`]))
  }
  sheet.etc = applyLines(sheet.etc, got.e)
  sheet.requests = applyLines(sheet.requests, got.r)
}
const boxes = () => [...halves.value.flatMap((half, h) => [[`${half}학습 진도`, sheet.progress[h]], [`${half}학습 이해도`, sheet.understanding[h]]]), ['기타', sheet.etc], ['건의사항', sheet.requests]]
const safe = (res) => {
  // 아동 안전 신호가 있으면 서버가 초안을 만들지 않고 운영사무국 안내만 돌려준다: 그 안내를 보여 주고 저장하지 않는다
  if (!Object.keys(res.draft).length) throw new Error(res.warnings[0] || '보고서를 정리하지 못했습니다.')
  if (res.error) throw new Error('AI의 답을 읽지 못해 다듬지 못했습니다. 잠시 뒤 다시 눌러 주세요.')   // 형식 오류를 '바꿀 표현이 없었습니다'로 넘기지 않는다
  return res
}

async function run(name, fn) {
  error.value = ''
  notes.value = []
  busy.value = name
  try {
    await fn()
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = ''
  }
}

// 표현 다듬기: 새로 적거나 고친 줄만 AI에 보낸다. 규칙으로 넣은 학습 진도 줄과 이미 다듬은 줄은 보내지 않는다. 학습 내용은 계획에서 온 글이라 다듬지 않는다
const polish = () => run('polish', async () => {
  const snap = boxes(), undo = JSON.parse(JSON.stringify(sheet))
  const whole = tagged()
  const fresh = {}, send = {}, labels = {}
  for (const k of Object.keys(whole)) {
    // '출결:' 같은 머리말은 떼고 보낸다. 머리말뿐인 줄은 보내지 않는다
    const lines = freshLines(whole[k], polished[k], k === 'attendance' ? toLines([['p0', auto.join('\n')]]) : '').map((l) => [l, ...splitLabel(l)]).filter(([, body]) => body)
    if (lines.length) Object.assign(fresh, { [k]: lines.map((x) => x[0]) }), Object.assign(send, { [k]: lines.map((x) => x[1]) }), Object.assign(labels, { [k]: lines.map((x) => x[2]) })
  }
  const only = Object.keys(fresh)
  if (!only.length) return toast('새로 다듬을 내용이 없습니다. 학습 이해도처럼 직접 적은 글을 다듬습니다.')
  const res = safe(await api.draft(FORM_ID, payload({ ...whole, ...Object.fromEntries(only.map((k) => [k, send[k].join('\n')])) }), { only, keep_lines: true, duration: profile.value?.duration }))
  const kept = []
  for (const k of only) {
    const got = String(res.draft[k] || '').split('\n').filter((l) => l.trim())
    const merged = mergeLines(whole[k], fresh[k], got.length === fresh[k].length ? got.map((l, i) => joinLabel(l, labels[k][i])).join('\n') : got.join('\n'))
    if (merged === null) kept.push('일부 글은 다듬은 결과의 줄 수가 달라 적어 둔 그대로 두었습니다. 넣지 않는 내용이 빠졌을 수 있으니 저장할 때 확인해 주세요.')
    else polished[k] = whole[k] = merged
  }
  restore(whole)
  const items = boxes().flatMap(([label, after], i) => changedLines(snap[i][1], after).map(([b, a]) => ({ label, before: b, after: a })))
  changes.value = items.length ? { items, undo } : null
  notes.value = [...kept, ...(res.pii_masked.length ? [`AI에 보내기 전에 가린 정보: ${res.pii_masked.join(', ')}`] : []), ...res.warnings]
  toast(changes.value ? '표현을 다듬었습니다. 바뀐 내용을 확인하고 저장해 주세요.' : '다듬어 보았지만 바꿀 표현이 없었습니다.')
})
function undoChanges() {
  Object.assign(sheet, changes.value.undo)
  for (const k of Object.keys(polished)) delete polished[k]
  changes.value = null
  toast('AI가 바꾸기 전으로 되돌렸습니다.')
}

// 저장은 AI를 쓰지 않는다. 서버가 개인정보를 가리고 넣지 않는 내용(정서·가정·건강)을 뺀 글을 칸에 다시 넣고 저장한다
const line = (text, label) => String(text || '').split('\n').map((l) => l.trim()).find((l) => l.startsWith(`${label}:`)) || ''
const save = () => run('save', async () => {
  const sent = payload(tagged())
  const res = safe(await api.draft(FORM_ID, sent, { only: [], keep_lines: true, duration: profile.value?.duration }))
  if (!absent.value) sheet.content = String(res.draft.scope || '')
  restore(res.draft)
  // 완료보고서와 인계 요약이 읽는 글: 이름표 없이, 시간확대면 전반·후반을 밝혀 둔다
  const joined = (list) => list.map((t, h) => t.trim() && [halves.value[h].trim(), t.trim()].filter(Boolean).join('\n')).filter(Boolean).join('\n')
  const progress = absent.value ? '' : sheet.progress[0]
  const readable = { attendance: line(progress, '출결').replace(/^출결:\s*/, '') || (q.status === '출석' ? '정시 출석' : q.status), lecture_progress: line(progress, '인강'), homework: line(progress, '과제'),
    progress_note: absent.value ? '' : joined(sheet.progress), session_content: absent.value ? String(res.draft.session_content || '') : joined(sheet.understanding),
    etc: sheet.etc.trim(), requests: sheet.requests.trim() }
  const item = await saveItem({ id: savedId.value, alias, formId: FORM_ID, title: `활동보고서 ${no.value}회차`, sessionNo: no.value, inputs: { ...sent, ...readable }, draft: { ...res.draft, ...readable },
    extra: { quick: { ...q }, sheet: JSON.parse(JSON.stringify(sheet)), auto } })
  savedId.value = item.id
  changes.value = null   // 저장한 글이 기준이다: 저장 전의 되돌리기는 남기지 않는다
  // 지금 회차를 저장했으면 다음 회차(마지막 회차였으면 완료보고서)로 넘어갈 수 있다
  const step = profile.value ? afterReport(profile.value, no.value) : {}
  if (Object.keys(step).length) {
    const { _id, ...rest } = profile.value
    await saveItem({ id: _id, alias, formId: 'mentee_profile', title: '멘티 정보', draft: { ...rest, ...step } })
  }
  const empty = absent.value ? [] : boxes().filter(([label, text]) => /학습 (진도|이해도)$/.test(label) && !text.trim()).map(([label]) => label)
  if (!sheet.content.trim()) empty.unshift('이번 주차 학습 내용')
  notes.value = [...(empty.length ? [`비어 있는 칸이 있습니다: ${empty.join(', ')}. 플랫폼에 제출하기 전에 채워 주세요.`] : []),
    ...(res.pii_masked.length ? [`가린 정보: ${res.pii_masked.join(', ')}`] : []), ...res.warnings, ...res.reminders]
  next.value = step.stage ? '완료보고서' : step.currentRound ? `${step.currentRound}회차` : ''
  toast(step.stage ? '저장했습니다. 마지막 회차입니다. 다음은 완료보고서입니다.' : step.currentRound ? `저장했습니다. 다음은 ${step.currentRound}회차입니다.` : '저장했습니다.')
  if (!next.value) emit('saved')
})
</script>

<template>
  <div :class="{ shell: !embedded }">
    <template v-if="!embedded">
      <MenteeHeader :alias="alias" :title="`활동보고서 ${no}회차`" />
      <h1>{{ no }}회차 활동보고서</h1>
    </template>
    <p class="muted">칸마다 [복사]해 플랫폼의 같은 칸에 붙여 넣어 주세요. 평가는 플랫폼에서 직접 고릅니다. 멘토링 후 7일 이내에 제출해 주세요.</p>
    <div v-if="error" class="box error">{{ error }}</div>
    <p v-if="savedId && !next" class="box ask" data-test="reopened">저장해 둔 {{ no }}회차 활동보고서입니다. 고쳐서 다시 저장할 수 있습니다.</p>

    <form v-if="loaded" class="card plan-form" @submit.prevent="save">
      <!-- 서버 응답을 기다리는 동안에는 입력을 잠근다: 그 사이에 적은 글이 응답으로 덮이지 않게 -->
      <fieldset :disabled="!!busy">
      <section class="form-section">
        <div class="form-grid">
          <label class="field"><span class="name">회차 상태</span><select v-model="q.status" data-q="status"><option v-for="s in statusesOf(profile?.mode)" :key="s">{{ s }}</option></select></label>
          <label class="field"><span class="name">진행일</span><input v-model="q.date" type="date" required data-q="date" /></label>
          <label class="field"><span class="name">진행시간 (실제 접속시간)</span><input v-model="q.time" placeholder="예: 17:03~18:05" data-q="time" />
            <span v-if="!absent" class="notice">계획한 일정으로 채웠습니다. 플랫폼 접속 기록과 같은 실제 시작~종료 시간으로 고쳐 주세요.</span></label>
        </div>
        <p v-if="absent" class="notice">진행하지 못한 회차는 학습 진도와 학습 이해도를 적지 않습니다. 저장하면 필요한 증빙을 안내해 드립니다.</p>
      </section>

      <section v-if="!absent" class="form-section">
        <h3>인강과 지난 회차 과제 확인</h3>
        <div v-if="what.lecture || what.task || prevHw?.sentences.length" class="mini" data-test="prev-homework">
          <template v-if="what.lecture"><span class="t">{{ prevHw?.lecture ? '지난 회차에 낸 인강' : '이번 주차 계획의 인강' }}</span>{{ what.lecture }}<br /></template>
          <template v-if="what.task"><span class="t">지난 회차에 낸 과제</span>{{ what.task }}<br /></template>
          <template v-if="prevHw?.sentences.length"><span class="t">지난 회차 보고서에 적은 과제</span>{{ prevHw.sentences.join(' ') }}</template>
        </div>
        <div class="form-grid">
          <div class="field"><span class="name">인강 수강</span>
            <span class="choices" role="radiogroup" aria-label="인강 수강"><label><input v-model="q.lectureDone" type="radio" value="함" name="lecture" />들음</label><label><input v-model="q.lectureDone" type="radio" value="안 함" name="lecture" />안 들음</label></span></div>
          <div class="field"><span class="name">과제 수행</span>
            <span class="choices" role="radiogroup" aria-label="과제 수행"><label><input v-model="q.taskDone" type="radio" value="함" name="task" />함</label><label><input v-model="q.taskDone" type="radio" value="안 함" name="task" />안 함</label></span></div>
        </div>
        <p class="notice">고르면 아래 학습 진도에 '인강: …', '과제: …' 줄로 들어갑니다. 일부만 했다면 그 줄을 직접 고쳐 주세요.</p>
      </section>

      <div class="item">
        <div class="head"><strong>이번 주차 학습 내용</strong><button type="button" class="small" :disabled="!sheet.content.trim()" data-copy="content" @click="copy('이번 주차 학습 내용', sheet.content)">복사</button></div>
        <textarea v-model="sheet.content" :rows="Math.max(3, sheet.content.split('\n').length + 1)" placeholder="학습범위: 거듭제곱근과 지수법칙&#10;학습목표: 거듭제곱근의 개념을 이해하고 지수법칙을 적용해 식을 계산할 수 있다" aria-label="이번 주차 학습 내용" data-sheet="content"></textarea>
        <span v-if="!absent" class="notice">{{ planned ? `종합계획서의 ${no}주차 계획을 가져왔습니다. 다르게 진행했다면 고쳐 주세요. ` : '' }}학습범위(혹은 목차)와 학습목표를 적습니다.</span>
      </div>

      <template v-if="!absent">
        <template v-for="(half, h) in halves" :key="h">
          <div class="item" :data-item="`progress-${h}`">
            <div class="head"><strong>{{ half }}학습 진도</strong><button type="button" class="small" :disabled="!sheet.progress[h].trim()" :data-copy="`progress-${h}`" @click="copy(`${half}학습 진도`, sheet.progress[h])">복사</button></div>
            <textarea v-model="sheet.progress[h]" :rows="Math.max(3, sheet.progress[h].split('\n').length + 1)" placeholder="출결: 5분 전 도착&#10;인강: 거듭제곱근과 지수법칙 3강 수강, 4강 미수강&#10;과제: 인강 교재를 수강 범위만큼 풀고 채점했으나 오답 풀이는 하지 않음" :aria-label="`${half}학습 진도`" :data-box="`progress-${h}`"></textarea>
            <span class="notice">{{ h === 0 ? '위에서 고른 것으로 채웠습니다. 잘한 점, 부족한 점, 개선 방향을 덧붙여도 됩니다.' : '후반 1시간의 진도를 직접 적어 주세요. 출결과 인강·과제 확인은 전반에 들어 있습니다.' }}</span>
          </div>
          <div class="item" :data-item="`understanding-${h}`">
            <div class="head"><strong>{{ half }}학습 이해도</strong><button type="button" class="small" :disabled="!sheet.understanding[h].trim()" :data-copy="`understanding-${h}`" @click="copy(`${half}학습 이해도`, sheet.understanding[h])">복사</button></div>
            <textarea v-model="sheet.understanding[h]" :rows="Math.max(4, sheet.understanding[h].split('\n').length + 1)" placeholder="예습이 되어 거듭제곱근 개념 설명을 잘 이해함&#10;계산 실수 잦음, 지수법칙 계산 문제 반복&#10;못 들은 강의는 다음 멘토링 시간까지 듣도록 과제로 냄" :aria-label="`${half}학습 이해도`" :data-box="`understanding-${h}`"></textarea>
            <span v-if="h === 0" class="notice">멘토링에서 한 내용과 멘티의 이해도를 한 줄에 하나씩 적어 주세요. 다음 회차까지 낸 인강·과제도 여기에 적습니다. 짧은 메모로 적고 [AI로 표현 다듬기]를 누르면 문장으로 고쳐 드립니다.</span>
          </div>
        </template>
      </template>

      <div class="item" data-item="etc">
        <div class="head"><strong>기타 <span class="tag">선택</span></strong><button type="button" class="small" :disabled="!sheet.etc.trim()" data-copy="etc" @click="copy('기타', sheet.etc)">복사</button></div>
        <textarea v-model="sheet.etc" rows="2" placeholder="학습사이트, 멘토링 공간, 진행과 관련해 전할 내용. 예: 화상 화면이 자주 끊깁니다. 확인 부탁드립니다." aria-label="기타" data-box="etc"></textarea>
      </div>

      <div class="item">
        <div class="head"><strong>건의사항 <span class="tag">선택</span></strong><button type="button" class="small" :disabled="!sheet.requests.trim()" data-copy="requests" @click="copy('건의사항', sheet.requests)">복사</button></div>
        <textarea v-model="sheet.requests" rows="2" placeholder="멘토링 일정 변경, 장소 변경 등. 예: 다음 주는 멘티의 수학여행으로 진행하지 않습니다." aria-label="건의사항" data-sheet="requests"></textarea>
      </div>
      <p class="notice">멘티 이름·연락처·학교는 쓰지 마세요. 적혀 있으면 저장하거나 AI에 보내기 전에 가립니다. 정서·가정 이야기는 보고서에 넣지 않습니다.</p>

      <div v-if="changes" class="box ask changes" data-test="changes">
        <div class="row"><strong class="grow">AI가 표현을 다듬은 곳 {{ changes.items.length }}곳</strong><button type="button" class="small" data-test="undo" @click="undoChanges">되돌리기</button></div>
        <ul><li v-for="(c, i) in changes.items" :key="i"><b>{{ c.label }}</b><del v-if="c.before.trim()">{{ c.before }}</del><ins>{{ c.after || '(비워짐)' }}</ins></li></ul>
      </div>
      <div v-if="notes.length" class="box warn" data-test="notes"><ul><li v-for="n in notes" :key="n">{{ n }}</li></ul></div>
      <div class="row">
        <button class="primary" :disabled="!!busy" data-test="save">{{ busy === 'save' ? '저장하는 중…' : '저장' }}</button>
        <button type="button" :disabled="!!busy || absent" data-test="polish" @click="polish">{{ busy === 'polish' ? '다듬는 중…' : 'AI로 표현 다듬기' }}</button>
        <button v-if="next && embedded" type="button" class="primary" data-test="next-round" @click="emit('saved')">{{ next }}로 넘어가기</button>
        <router-link v-if="!embedded" :to="menteePath(alias)" class="linkbutton">멘티 화면으로 돌아가기</router-link>
      </div>
      </fieldset>
    </form>
  </div>
</template>
