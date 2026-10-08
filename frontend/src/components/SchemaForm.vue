<script setup>
// 양식 스키마에서 만든 입력 칸 목록(fields)을 그대로 그린다. 양식이 바뀌어도 이 컴포넌트는 고치지 않는다.
const props = defineProps({ fields: { type: Array, required: true }, modelValue: { type: Object, required: true } })
const emit = defineEmits(['update:modelValue'])

function set(key, value) {
  emit('update:modelValue', { ...props.modelValue, [key]: value })
}
</script>

<template>
  <div>
    <label v-for="f in fields" :key="f.key" class="field">
      <span class="name">{{ f.label }}<span v-if="f.required" class="req">*</span></span>
      <select v-if="f.control === 'select'" :value="modelValue[f.key]" :data-key="f.key" @change="set(f.key, $event.target.value)">
        <option value="">선택해 주세요</option>
        <option v-for="o in f.options" :key="o" :value="o">{{ o }}</option>
      </select>
      <textarea v-else-if="f.control === 'textarea' || f.control === 'lines'" :value="modelValue[f.key]" :data-key="f.key"
        :placeholder="f.control === 'lines' ? '한 줄에 하나씩 적어 주세요' : f.example" @input="set(f.key, $event.target.value)"></textarea>
      <input v-else :type="f.control" :value="modelValue[f.key]" :data-key="f.key" :min="f.min" :max="f.max" :placeholder="f.example"
        @input="set(f.key, $event.target.value)" />
      <span v-if="f.guidance" class="notice">{{ f.guidance }}</span>
    </label>
  </div>
</template>
