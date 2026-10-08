<script setup>
import { computed } from 'vue'

// 양식 스키마에서 만든 입력 칸 목록(fields)을 그대로 그린다. 양식이 바뀌어도 이 컴포넌트는 고치지 않는다.
const props = defineProps({ fields: { type: Array, required: true }, modelValue: { type: Object, required: true } })
const emit = defineEmits(['update:modelValue'])

// 같은 group이 이어지는 칸끼리 묶는다
const groups = computed(() => {
  const out = []
  for (const f of props.fields) {
    const last = out[out.length - 1]
    if (last && last.title === f.group) last.fields.push(f)
    else out.push({ title: f.group, fields: [f] })
  }
  return out
})

function set(key, value) {
  emit('update:modelValue', { ...props.modelValue, [key]: value })
}

function grow(e) {
  e.target.style.height = 'auto'
  e.target.style.height = `${e.target.scrollHeight + 2}px`
}
</script>

<template>
  <div>
    <section v-for="g in groups" :key="g.title + g.fields[0].key" class="form-section">
      <h3 v-if="g.title">{{ g.title }}</h3>
      <div class="form-grid">
        <label v-for="f in g.fields" :key="f.key" class="field" :class="{ wide: f.control === 'textarea' || f.control === 'lines' || f.label.length > 22 }">
          <span class="name">{{ f.label }}<span v-if="f.required" class="req" aria-label="필수">*</span></span>
          <select v-if="f.control === 'select'" :value="modelValue[f.key]" :data-key="f.key" @change="set(f.key, $event.target.value)">
            <option value="">선택해 주세요</option>
            <option v-for="o in f.options" :key="o" :value="o">{{ o }}</option>
          </select>
          <textarea v-else-if="f.control === 'textarea' || f.control === 'lines'" :value="modelValue[f.key]" :data-key="f.key" rows="2"
            :placeholder="f.control === 'lines' ? '한 줄에 하나씩 적어 주세요' : f.example ? `예: ${f.example}` : ''"
            @input="set(f.key, $event.target.value); grow($event)"></textarea>
          <input v-else :type="f.control" :value="modelValue[f.key]" :data-key="f.key" :min="f.min" :max="f.max"
            :placeholder="f.example ? `예: ${f.example}` : ''" @input="set(f.key, $event.target.value)" />
          <span v-if="f.help" class="notice">{{ f.help }}</span>
        </label>
      </div>
    </section>
  </div>
</template>
