<script setup>
import { reactive, ref } from 'vue'
import { api } from '../api/client'

// 활동비 계산기. 활동가이드 기준을 규칙으로 계산한 추정 금액이다 (AI를 쓰지 않는다).
const f = reactive({ mode: '온라인', normal: 4, no_show: 0, late_cancel: 0, stage: 1, extra: 'none', hours: 1, monthly: '' })
const res = ref(null)
const error = ref('')
const won = (n) => `${Number(n).toLocaleString('ko-KR')}원`

async function calc() {
  error.value = ''
  try {
    const monthly_valid = f.monthly.split(/[,\s]+/).filter(Boolean).map(Number).filter((n) => Number.isInteger(n) && n >= 0)
    res.value = await api.allowance({
      mode: f.mode, normal: Number(f.normal) || 0, no_show: Number(f.no_show) || 0, late_cancel: Number(f.late_cancel) || 0,
      stage: Number(f.stage) || 1, senior: f.extra === 'senior', vulnerable: f.extra === 'vulnerable', hours: Number(f.hours), monthly_valid,
    })
  } catch (e) {
    error.value = e.message
  }
}
</script>

<template>
  <div class="shell">
    <h1>활동비 계산</h1>
    <p class="muted">활동가이드(p.41~47) 기준으로 계산한 추정 금액입니다. 실제 지급액은 활동보고서 승인 결과와 운영사무국 정산에 따릅니다.</p>
    <form class="card" @submit.prevent="calc">
      <div class="row">
        <label class="field" style="flex: 1"><span class="name">멘토링 유형</span><select v-model="f.mode"><option>온라인</option><option>오프라인</option></select></label>
        <label class="field" style="flex: 1"><span class="name">회차당 시간</span><select v-model="f.hours"><option :value="1">1시간</option><option :value="2">2시간 (시간확대)</option></select></label>
        <label v-if="f.mode === '온라인'" class="field" style="flex: 1"><span class="name">장기활동 가산금 구간</span>
          <select v-model="f.stage"><option v-for="n in 6" :key="n" :value="n">{{ n }}구간</option></select>
        </label>
      </div>
      <label class="field"><span class="name">가산금 (둘 중 하나만)</span>
        <select v-model="f.extra">
          <option value="none">해당 없음</option>
          <option value="senior">고학년지도 (멘티가 고등 과정 학습사이트 수강)</option>
          <option value="vulnerable">취약계층지원 (회기 종료 후 정산)</option>
        </select>
      </label>
      <div class="row">
        <label class="field" style="flex: 1"><span class="name">정상 진행한 회차 수</span><input v-model="f.normal" type="number" min="0" max="60" /></label>
        <label class="field" style="flex: 1"><span class="name">멘티 무단결석 회차 수</span><input v-model="f.no_show" type="number" min="0" max="60" /></label>
        <label v-if="f.mode === '온라인'" class="field" style="flex: 1"><span class="name">임박취소 회차 수</span><input v-model="f.late_cancel" type="number" min="0" max="60" /></label>
      </div>
      <label v-if="f.mode === '온라인'" class="field"><span class="name">달마다의 유효 진행 횟수 (선택)</span>
        <input v-model="f.monthly" placeholder="예: 5, 6, 6, 4, 7, 2" />
        <span class="notice">넣으면 달마다 가산금 구간이 어떻게 오르는지 보여 드립니다. 한 달에 4회 이상인 달이 2번 모이면 다음 달부터 1구간 오릅니다.</span>
      </label>
      <button class="primary">계산하기</button>
    </form>
    <div v-if="error" class="box error">{{ error }}</div>
    <template v-if="res">
      <div class="card" data-test="result">
        <strong>시간당 {{ won(res.hourly.total) }}</strong>
        <ul><li v-for="i in res.hourly.items" :key="i.name">{{ i.name }}: {{ won(i.amount) }}</li></ul>
        <strong>추정 합계 {{ won(res.total) }}</strong>
        <ul><li v-for="l in res.lines" :key="l.name">{{ l.name }} = {{ won(l.amount) }}</li></ul>
        <p v-if="res.later">나중에 정산: {{ res.later.name }} = {{ won(res.later.amount) }}</p>
      </div>
      <div v-if="res.months" class="card">
        <table>
          <tr><th>달</th><th>유효 진행</th><th>구간 적용 횟수</th><th>가산금 구간</th><th>시간당 (기본+장기활동)</th></tr>
          <tr v-for="m in res.months" :key="m.month"><td>{{ m.month }}번째 달</td><td>{{ m.valid }}회</td><td>{{ m.applied }}</td><td>{{ m.stage }}구간</td><td>{{ won(m.hourly) }}</td></tr>
        </table>
      </div>
      <div class="box warn"><ul><li v-for="n in res.notes" :key="n">{{ n }}</li><li>{{ res.disclaimer }}</li></ul></div>
      <p class="muted">근거: {{ res.sources.join(' / ') }}</p>
    </template>
  </div>
</template>
