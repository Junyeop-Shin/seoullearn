<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { api } from '../api/client'
import { monthRows, payInfo, reportMonths } from '../lib/allowance'
import { menteesFromVault } from '../lib/mentee'
import { reportsFromVault } from '../lib/reports'
import { loadSettings } from '../stores/settings'

// 활동비 계산. 활동가이드(p.41~47) 기준을 서버의 규칙 함수로 계산한 추정 금액이다 (AI를 쓰지 않는다).
// 저장해 둔 활동보고서의 진행일과 회차 상태로 한 달치 입력을 채우고, 멘토가 고쳐서 계산한다. 서버에는 회차 수와 조건만 보낸다 (이름은 보내지 않는다).
const STAGE_KEY = 'seoullearn.allowance.stage'   // 장기활동 가산금 구간은 과거 이력으로 정해져 자동으로 알 수 없다: 고른 값을 이 브라우저에 기억해 둔다
const won = (n) => `${Number(n).toLocaleString('ko-KR')}원`
const mentees = ref([])        // [{alias, profile, reports}]
const loaded = ref(false)
const months = computed(() => reportMonths(mentees.value))
const month = ref('')
const rows = ref([])           // 그 달의 멘티별 회차 수 (저장한 보고서로 채우고, 고쳐 쓸 수 있다)
const cond = reactive({ stage: Number(localStorage.getItem(STAGE_KEY)) || 1, vulnerable: false })
const res = ref(null)
const error = ref('')
const hasOnline = computed(() => rows.value.some((r) => r.mode === '온라인'))
const pay = computed(() => payInfo(month.value))
const volunteer = loadSettings().mentoringType === '봉사형'

onMounted(async () => {
  try {
    mentees.value = (await menteesFromVault()).map((m) => ({ ...m, reports: reportsFromVault(m.items) }))
    month.value = months.value[0] || ''
  } catch (e) {
    error.value = e.message
  } finally {
    loaded.value = true
  }
})
watch(month, () => { rows.value = monthRows(mentees.value, month.value) })
// 회차 수나 조건을 고치면 앞서 계산한 합계는 지운다 (입력과 결과가 서로 다른 값을 가리키지 않게)
watch([rows, cond], () => { res.value = null }, { deep: true })

async function calcMonth() {
  error.value = ''
  try {
    const n = (v) => Math.max(0, Math.floor(Number(v) || 0))
    localStorage.setItem(STAGE_KEY, String(cond.stage))
    res.value = await api.allowanceMonth({
      groups: rows.value.map((r) => ({ mode: r.mode, hours: r.hours, normal: n(r.normal), no_show: n(r.no_show), late_cancel: r.mode === '온라인' ? n(r.late_cancel) : 0, senior: !!r.senior })),
      stage: hasOnline.value ? Number(cond.stage) || 1 : 1, vulnerable: cond.vulnerable,   // 구간은 온라인에만 있다
    })
  } catch (e) {
    error.value = e.message
  }
}

// ---- 직접 넣어 계산 (보고서를 저장하지 않았거나 다른 경우를 따져 볼 때)
const f = reactive({ mode: '온라인', normal: 4, no_show: 0, late_cancel: 0, stage: 1, extra: 'none', hours: 1, monthly: '' })
const manual = ref(null)
const manualError = ref('')
async function calc() {
  manualError.value = ''
  try {
    const monthly_valid = f.monthly.split(/[,\s]+/).filter(Boolean).map(Number).filter((n) => Number.isInteger(n) && n >= 0)
    manual.value = await api.allowance({
      mode: f.mode, normal: Number(f.normal) || 0, no_show: Number(f.no_show) || 0, late_cancel: Number(f.late_cancel) || 0,
      stage: Number(f.stage) || 1, senior: f.extra === 'senior', vulnerable: f.extra === 'vulnerable', hours: Number(f.hours), monthly_valid,
    })
  } catch (e) {
    manualError.value = e.message
  }
}
</script>

<template>
  <div class="shell">
    <h1>활동비 계산</h1>
    <p class="muted">활동가이드(p.41~47) 기준으로 계산한 추정 금액입니다. 실제 지급액은 활동보고서 승인 결과와 운영사무국 정산에 따릅니다.</p>
    <div v-if="volunteer" class="box warn" data-test="volunteer">설정의 멘토링 유형이 봉사형입니다. 이 계산은 활동비를 받는 시급형 기준입니다. 봉사형의 인정 기준은 운영사무국에 확인해 주세요.</div>

    <h2>저장한 활동보고서로 계산</h2>
    <p v-if="loaded && !months.length" class="card muted" data-test="no-reports">저장한 활동보고서가 없습니다. 활동보고서를 저장하면 그 달의 회차 수를 여기에 채워 드립니다. 아래 '직접 넣어 계산'은 지금도 쓸 수 있습니다.</p>
    <form v-if="months.length" class="card" data-test="month-form" @submit.prevent="calcMonth">
      <div class="form-grid">
        <label class="field"><span class="name">계산할 달</span>
          <select v-model="month" data-test="month"><option v-for="m in months" :key="m" :value="m">{{ m.slice(0, 4) }}년 {{ Number(m.slice(5)) }}월</option></select>
        </label>
        <label v-if="hasOnline" class="field"><span class="name">장기활동 가산금 구간 (온라인)</span>
          <select v-model="cond.stage" data-test="stage"><option v-for="n in 6" :key="n" :value="n">{{ n }}구간{{ n === 1 ? ' (가산 없음)' : ` (${(n - 1) * 10}%)` }}</option></select>
          <span class="notice">활동 이력에 따라 정해지므로 직접 골라 주세요. 고른 값은 이 브라우저에 기억해 둡니다.</span>
        </label>
      </div>
      <table class="allowance" data-test="month-rows">
        <thead><tr><th>멘티</th><th>정상 진행</th><th>무단결석</th><th>임박취소</th><th>인정결석</th><th>고학년지도</th></tr></thead>
        <tbody>
          <tr v-for="r in rows" :key="r.alias" :data-row="r.alias">
            <td><strong>{{ r.name }}</strong><small>{{ r.mode }} · 회당 {{ r.hours }}시간</small></td>
            <td><input v-model="r.normal" type="number" min="0" max="31" :aria-label="`${r.name} 정상 진행 회차 수`" data-col="normal" /></td>
            <td><input v-model="r.no_show" type="number" min="0" max="31" :aria-label="`${r.name} 무단결석 회차 수`" data-col="no_show" /></td>
            <td><input v-if="r.mode === '온라인'" v-model="r.late_cancel" type="number" min="0" max="31" :aria-label="`${r.name} 임박취소 회차 수`" data-col="late_cancel" /><span v-else class="muted">해당 없음</span></td>
            <td>{{ r.excused }}회</td>
            <td><label class="check"><input v-model="r.senior" type="checkbox" :aria-label="`${r.name} 고학년지도 가산금`" data-col="senior" />대상</label></td>
          </tr>
        </tbody>
      </table>
      <ul class="notice">
        <li>저장한 활동보고서로 채웠습니다. 승인되지 않은 회차나 다음 회기를 시작하며 지운 회차가 있으면 숫자를 고쳐 주세요.</li>
        <li>출석과 지각은 정상 진행으로 세고, 인정결석은 금액에 넣지 않습니다.</li>
        <li>고학년지도는 수강 강좌 이름으로 짐작해 표시했습니다. 멘티가 고등학생용 학습사이트(이투스, 메가스터디, 밀크T 고등, 대성마이맥)를 수강할 때만 선택해 주세요.</li>
      </ul>
      <label class="check"><input v-model="cond.vulnerable" type="checkbox" data-test="vulnerable" />취약계층지원 가산금 대상입니다</label>
      <span class="notice">학자금지원구간 2구간 이하인 서울 소재 대학(원) 재학 멘토가 대상입니다. 회기가 끝난 뒤 멘토링 수기를 내고 승인받으면 따로 정산되고, 고학년지도 가산금과 함께 받을 수 없습니다.</span>
      <div class="row gap-top"><button class="primary" data-test="calc-month">계산하기</button></div>
    </form>
    <div v-if="error" class="box error">{{ error }}</div>
    <template v-if="res">
      <div class="card" data-test="month-result">
        <p class="total"><span>{{ pay.month }}월 활동비 추정 합계</span><strong data-test="month-total">{{ won(res.total) }}</strong></p>
        <p v-if="res.later_total" class="muted" data-test="month-later">취약계층지원 가산금 {{ won(res.later_total) }}은 회기가 끝난 뒤 따로 정산됩니다.</p>
        <div v-for="(g, i) in res.groups" :key="rows[i].alias" class="allowance-group">
          <div class="row"><strong class="grow">{{ rows[i].name }}<span class="tag">{{ g.mode }} · 회당 {{ rows[i].hours }}시간</span></strong><strong>{{ won(g.total) }}</strong></div>
          <ul><li v-for="l in g.lines" :key="l.name">{{ l.name }} = {{ won(l.amount) }}</li><li v-if="g.later">나중에 정산: {{ g.later.name }} = {{ won(g.later.amount) }}</li></ul>
        </div>
      </div>
      <div class="box warn" data-test="month-notes"><ul>
        <li>{{ pay.month }}월 활동비는 {{ pay.payMonth }}월 20일에 지급됩니다. {{ pay.month }}월 말일까지 제출기한(멘토링 후 7일) 안에 등록해 승인된 활동보고서가 대상입니다.</li>
        <li v-for="n in res.notes" :key="n">{{ n }}</li>
      </ul></div>
      <p class="muted">근거: {{ res.sources.join(' / ') }}</p>
    </template>

    <h2>직접 넣어 계산</h2>
    <details class="card" :open="loaded && !months.length" data-test="manual">
      <summary>회차 수와 조건을 직접 넣어 계산하기</summary>
      <form @submit.prevent="calc">
        <div class="row">
          <label class="field grow"><span class="name">멘토링 방식</span><select v-model="f.mode"><option>온라인</option><option>오프라인</option></select></label>
          <label class="field grow"><span class="name">회당 시간</span><select v-model="f.hours"><option :value="1">1시간</option><option :value="2">2시간 (시간확대)</option></select></label>
          <label v-if="f.mode === '온라인'" class="field grow"><span class="name">장기활동 가산금 구간</span>
            <select v-model="f.stage"><option v-for="n in 6" :key="n" :value="n">{{ n }}구간{{ n === 1 ? ' (가산 없음)' : ` (${(n - 1) * 10}%)` }}</option></select>
          </label>
        </div>
        <label class="field"><span class="name">가산금 (둘 중 하나만)</span>
          <select v-model="f.extra">
            <option value="none">해당 없음</option>
            <option value="senior">고학년지도 (멘티가 고등 과정 학습사이트 수강)</option>
            <option value="vulnerable">취약계층지원 (멘토가 대상일 때, 회기 종료 후 정산)</option>
          </select>
        </label>
        <div class="row">
          <label class="field grow"><span class="name">정상 진행 회차 수</span><input v-model="f.normal" type="number" min="0" max="60" /></label>
          <label class="field grow"><span class="name">무단결석 회차 수</span><input v-model="f.no_show" type="number" min="0" max="60" /></label>
          <label v-if="f.mode === '온라인'" class="field grow"><span class="name">임박취소 회차 수</span><input v-model="f.late_cancel" type="number" min="0" max="60" /></label>
        </div>
        <label v-if="f.mode === '온라인'" class="field"><span class="name">달마다의 유효 진행 횟수 (선택)</span>
          <input v-model="f.monthly" placeholder="예: 5, 6, 6, 4, 7, 2" />
          <span class="notice">넣으면 달마다 가산금 구간이 어떻게 오르는지 보여 드립니다. 한 달에 4회 이상인 달이 2번 모이면 다음 달부터 1구간 오릅니다.</span>
        </label>
        <button class="primary" data-test="calc-manual">계산하기</button>
      </form>
      <div v-if="manualError" class="box error">{{ manualError }}</div>
      <template v-if="manual">
        <div class="mini gap-top" data-test="result">
          <strong>시간당 {{ won(manual.hourly.total) }}</strong>
          <ul><li v-for="i in manual.hourly.items" :key="i.name">{{ i.name }}: {{ won(i.amount) }}</li></ul>
          <strong>추정 합계 {{ won(manual.total) }}</strong>
          <ul><li v-for="l in manual.lines" :key="l.name">{{ l.name }} = {{ won(l.amount) }}</li></ul>
          <p v-if="manual.later">나중에 정산: {{ manual.later.name }} = {{ won(manual.later.amount) }}</p>
        </div>
        <table v-if="manual.months" class="allowance">
          <thead><tr><th>달</th><th>유효 진행</th><th>구간 적용 횟수</th><th>가산금 구간</th><th>시간당 (기본+장기활동)</th></tr></thead>
          <tbody><tr v-for="m in manual.months" :key="m.month"><td>{{ m.month }}번째 달</td><td>{{ m.valid }}회</td><td>{{ m.applied }}</td><td>{{ m.stage }}구간</td><td>{{ won(m.hourly) }}</td></tr></tbody>
        </table>
        <div v-if="manual.notes.length" class="box warn"><ul><li v-for="n in manual.notes" :key="n">{{ n }}</li></ul></div>
        <p class="muted">근거: {{ manual.sources.join(' / ') }}</p>
      </template>
    </details>
  </div>
</template>
