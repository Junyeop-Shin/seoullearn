<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { DISTRICTS, PROFILE_FORM, SUBJECTS, emptyProfile, menteePath } from '../lib/mentee'
import { flow, totalRounds } from '../lib/stage'
import { listAliases, saveItem } from '../stores/vault'

// 멘티 등록. 이미 진행 중인 멘티는 회기·회차(또는 단계)를 받아 그 지점부터 시작한다.
const router = useRouter()
const f = reactive({ name: '', grade: '', subject: '', subjectEtc: '', district: '', mode: '온라인', duration: '60',
  ongoing: false, term: 1, currentRound: 1, stage: 'ACTIVITY', course: '', lastLecture: '', lastTask: '' })
const error = ref('')

async function submit() {
  error.value = ''
  try {
    const taken = await listAliases()
    let alias = f.name.trim()
    if (!alias) {
      let n = taken.length + 1
      while (taken.includes(`멘티 ${n}`)) n += 1
      alias = `멘티 ${n}`
    }
    if (alias === 'new') throw new Error('이 이름은 쓸 수 없습니다. 다른 이름을 적어 주세요.')
    if (taken.includes(alias)) throw new Error('같은 이름으로 등록한 멘티가 이미 있습니다. 이름 뒤에 숫자를 붙여 주세요.')
    const p = { ...emptyProfile(), name: alias, grade: f.grade.trim(), subject: f.subject, subjectEtc: f.subjectEtc.trim(), district: f.district, mode: f.mode,
      duration: f.duration, stage: 'PRE_CONTACT' }
    if (f.ongoing) {
      // 회차는 활동보고서 단계에서만 받는다 (다른 단계로 바꾸면 칸이 사라지므로 적어 둔 값을 쓰지 않는다). 그 회기의 회차 수를 넘지 않게 한다
      Object.assign(p, { term: Number(f.term) || 1, stage: f.stage, course: f.course.trim() })
      p.currentRound = f.stage === 'ACTIVITY' ? Math.min(Number(f.currentRound) || 1, totalRounds(p)) : 1
      if (f.stage === 'COMPLETION') p.currentRound = totalRounds(p)   // 완료보고서 단계는 마지막 회차까지 마친 것이다
      if (f.lastLecture.trim() || f.lastTask.trim()) p.lastHomework = { lecture: f.lastLecture.trim(), task: f.lastTask.trim() }
    }
    await saveItem({ alias, formId: PROFILE_FORM, title: '멘티 정보', draft: p })
    router.push(menteePath(alias))
  } catch (e) {
    error.value = e.message
  }
}
</script>

<template>
  <div class="shell">
    <h1>멘티 등록</h1>
    <p class="muted">등록하면 메뉴에 멘티가 생기고, 사전 연락부터 완료보고서까지 단계 순서대로 진행합니다.</p>
    <form class="card" @submit.prevent="submit">
      <div class="form-grid">
        <label class="field"><span class="name">멘티 이름</span>
          <input v-model="f.name" placeholder="예: 김민수" maxlength="30" data-reg="name" />
          <span class="notice">이 브라우저에만 저장하고, 글에 이 이름이 나오면 AI로 보내기 전에 가립니다. 비워 두면 '멘티 1'처럼 붙여 드립니다.</span>
        </label>
        <label class="field"><span class="name">학년</span><input v-model="f.grade" placeholder="예: 고1" maxlength="10" data-reg="grade" /></label>
        <label class="field"><span class="name">신청 과목<span class="req">*</span></span>
          <select v-model="f.subject" required data-reg="subject"><option value="">선택해 주세요</option><option v-for="s in SUBJECTS" :key="s">{{ s }}</option></select>
        </label>
        <label v-if="f.subject === '기타'" class="field"><span class="name">기타 과목 이름<span class="req">*</span></span><input v-model="f.subjectEtc" maxlength="30" required placeholder="예: 검정고시 수학" data-reg="subjectEtc" /></label>
        <label class="field"><span class="name">자치구<span class="req">*</span></span>
          <select v-model="f.district" required data-reg="district"><option value="">선택해 주세요</option><option v-for="d in DISTRICTS" :key="d">{{ d }}</option></select>
          <span class="notice">협약 장소와 이음단 채널을 찾는 기준입니다.</span>
        </label>
        <label class="field"><span class="name">멘토링 방식<span class="req">*</span></span>
          <select v-model="f.mode" data-reg="mode"><option>온라인</option><option>오프라인</option></select>
          <span class="notice">오프라인이면 메뉴의 '오프라인 일정·장소'에서 장소와 일정을 이음단에 요청합니다.</span>
        </label>
        <label class="field"><span class="name">회당 학습시간</span>
          <select v-model="f.duration" data-reg="duration"><option value="60">60분 (16주)</option><option value="120">120분, 시간확대 (8주)</option></select>
        </label>
      </div>
      <label class="check"><input v-model="f.ongoing" type="checkbox" data-reg="ongoing" /> 이미 진행 중인 멘티입니다</label>
      <div v-if="f.ongoing" class="form-grid" data-test="ongoing">
        <label class="field"><span class="name">현재 회기</span><input v-model.number="f.term" type="number" min="1" data-reg="term" /></label>
        <label class="field"><span class="name">현재 단계</span>
          <select v-model="f.stage" data-reg="stage"><option v-for="s in flow({ term: f.term })" :key="s.id" :value="s.id">{{ s.label }}</option></select>
        </label>
        <label v-if="f.stage === 'ACTIVITY'" class="field"><span class="name">이번에 쓸 회차</span><input v-model.number="f.currentRound" type="number" min="1" :max="totalRounds(f)" data-reg="currentRound" /></label>
        <label class="field wide"><span class="name">학습사이트와 수강 강좌 <span class="tag">선택</span></span><input v-model="f.course" placeholder="예: 메가스터디 수학의 시작, 시발점 - 수1" data-reg="course" /></label>
        <label class="field"><span class="name">직전 회차에 낸 인강 분량 <span class="tag">선택</span></span><input v-model="f.lastLecture" placeholder="예: 5~6강" data-reg="lastLecture" /></label>
        <label class="field"><span class="name">직전 회차에 낸 과제 <span class="tag">선택</span></span><input v-model="f.lastTask" placeholder="예: 5강 예제 풀기" data-reg="lastTask" /></label>
        <p class="notice wide">이전 활동보고서가 없어, 다음 보고서의 '인강과 지난 회차 과제 확인'에 쓸 내용을 여기에 적어 주세요.</p>
      </div>
      <div v-if="error" class="box error" role="alert">{{ error }}</div>
      <div class="row"><button class="primary" data-test="register">멘티 등록</button></div>
    </form>
  </div>
</template>
