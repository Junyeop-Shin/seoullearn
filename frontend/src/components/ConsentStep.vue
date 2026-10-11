<script setup>
import { computed, reactive } from 'vue'
import { COLLECTED, CONSENTS, OVERSEAS, VERSION } from '../lib/privacy'

// 회원가입 전 동의. 항목마다 따로 동의를 받고(개인정보 보호법 제22조), 미리 체크해 두지 않는다.
// 알려야 하는 사항(항목, 목적, 보유 기간, 거부할 권리)은 접어 두지 않고 그 자리에서 보여 준다.
const emit = defineEmits(['agreed', 'cancel'])
const checked = reactive(Object.fromEntries(CONSENTS.map((c) => [c.id, false])))
const all = computed({ get: () => CONSENTS.every((c) => checked[c.id]), set: (v) => CONSENTS.forEach((c) => { checked[c.id] = v }) })
</script>

<template>
  <form class="consent" data-test="consent" @submit.prevent="emit('agreed', { version: VERSION, items: CONSENTS.map((c) => c.id) })">
    <h2>가입 전 동의</h2>
    <p class="muted">꼭 필요한 정보만 받습니다. 이름, 전자우편, 전화번호, 학교는 받지 않습니다. 내용을 읽고 항목마다 동의해 주세요.</p>
    <label class="check all"><input v-model="all" type="checkbox" data-consent="all" />아래 내용을 모두 읽었고 전부 동의합니다</label>

    <section v-for="c in CONSENTS" :key="c.id" class="term">
      <label class="check"><input v-model="checked[c.id]" type="checkbox" required :data-consent="c.id" /><span>{{ c.label }} <span class="tag">필수</span></span></label>

      <p v-if="c.id === 'age14'" class="notice">만 14세 미만은 법정대리인의 동의가 필요하지만 이 서비스에는 그 절차가 없어 가입할 수 없습니다.</p>

      <template v-else-if="c.id === 'collect'">
        <div class="scroll"><table class="terms">
          <thead><tr><th>수집하는 항목</th><th>수집·이용 목적</th><th>보유·이용 기간</th></tr></thead>
          <tbody><tr v-for="r in COLLECTED" :key="r.items"><td><strong>{{ r.items }}</strong></td><td>{{ r.purpose }}</td><td><strong>{{ r.period }}</strong></td></tr></tbody>
        </table></div>
        <p class="notice">비밀번호는 되돌릴 수 없게 암호화해 저장합니다. 멘토 설정(이름, 연락처, 대학교, 전공)과 멘티 정보, 작성한 문서는 이 브라우저에만 저장하고 서버로 보내지 않습니다. 탈퇴는 멘토 설정 화면에서 바로 할 수 있고, 탈퇴하면 계정 정보를 즉시 지웁니다.</p>
      </template>

      <template v-else-if="c.id === 'overseas'">
        <p class="notice">답변과 초안 문장은 국외의 AI 제공사가 만듭니다. 보내기 전에 서버가 이름, 전화번호, 학교명 같은 정보를 가립니다.</p>
        <dl class="terms"><template v-for="[k, v] in OVERSEAS" :key="k"><dt>{{ k }}</dt><dd>{{ v }}</dd></template></dl>
      </template>

      <p v-else-if="c.id === 'mentee'" class="notice">멘티는 미성년자입니다. 멘티의 실명, 연락처, 학교, 주소와 건강·가정 사정처럼 멘티를 알아볼 수 있거나 민감한 내용을 질문과 보고서 칸에 적지 않습니다. 적혀 있으면 가려서 보내지만 가리는 규칙이 모든 표현을 잡지는 못합니다. 멘티 이름 칸에 적은 이름은 이 브라우저에만 저장하고, 질문과 보고서에 그 이름이 나오면 보내기 전에 브라우저에서 가립니다.</p>
    </section>

    <p class="notice">동의를 거부할 권리가 있습니다. 다만 모두 서비스를 제공하는 데 꼭 필요한 항목이라, 동의하지 않으면 가입할 수 없습니다.</p>
    <div class="row">
      <button type="button" data-test="consent-cancel" @click="emit('cancel')">취소</button>
      <span class="grow"></span>
      <button class="primary" :disabled="!all" data-test="consent-ok">동의하고 계속</button>
    </div>
    <p class="muted switch"><a href="/privacy" target="_blank" rel="noopener">개인정보 처리방침 전문 보기</a> · 시행일 {{ VERSION }}</p>
  </form>
</template>
