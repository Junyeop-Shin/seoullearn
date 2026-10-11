<script setup>
// 메뉴 아이콘 (선으로 그린 작은 그림). 꾸밈용이라 화면낭독기에는 읽히지 않게 한다.
defineProps({ name: { type: String, required: true } })
const PATHS = {
  chat: 'M4 5h16v11H9l-5 4z',
  phone: 'M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a1 1 0 0 1-1 1A15 15 0 0 1 4 5a1 1 0 0 1 1-1z',
  pin: 'M12 21s7-6 7-11a7 7 0 0 0-14 0c0 5 7 11 7 11zM12 12.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5z',
  folder: 'M3 6h6l2 2h10v11H3z',
  calc: 'M6 3h12v18H6zM9 7h6M9 12h1M12 12h1M15 12h0M9 16h1M12 16h1M15 16h0',
  archive: 'M4 5h16v4H4zM5 9v10h14V9M10 13h4',
  settings: 'M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7zM4 12h2M18 12h2M12 4v2M12 18v2M6.3 6.3l1.4 1.4M16.3 16.3l1.4 1.4M6.3 17.7l1.4-1.4M16.3 7.7l1.4-1.4',
  people: 'M9 11a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7zM3 20c0-3.3 2.7-6 6-6s6 2.7 6 6M16 4.5a3.5 3.5 0 0 1 0 6.5M21 20c0-2.6-1.6-4.8-4-5.6',
  shield: 'M12 3l7 3v6c0 4-3 7-7 9-4-2-7-5-7-9V6z',
  plus: 'M12 5v14M5 12h14',
  calendar: 'M5 6h14v14H5zM5 10h14M9 3v4M15 3v4',
}
</script>

<template>
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <path :d="PATHS[name]" />
  </svg>
</template>
