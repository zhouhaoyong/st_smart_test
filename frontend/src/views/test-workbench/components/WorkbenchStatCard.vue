<template>
  <button class="workbench-stat-card" :class="`tone-${tone}`" type="button" @click="$emit('click')">
    <span class="stat-label">{{ label }}</span>
    <span class="stat-row">
      <span class="stat-icon"><el-icon :size="24"><component :is="icon" /></el-icon></span>
      <strong>{{ value }}</strong>
    </span>
    <span class="stat-action">查看明细</span>
  </button>
</template>

<script setup>
defineProps({
  label: { type: String, required: true },
  value: { type: [Number, String], default: 0 },
  icon: { type: [Object, Function], required: true },
  tone: { type: String, default: 'blue' },
})

defineEmits(['click'])
</script>

<style scoped>
.workbench-stat-card {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  justify-content: center;
  min-height: 120px;
  padding: 28px;
  overflow: hidden;
  color: #303133;
  font: inherit;
  text-align: left;
  cursor: pointer;
  border-radius: 14px;
  transition: transform .18s ease, box-shadow .18s ease;
}
.workbench-stat-card::after { content: ''; position: absolute; top: -30px; right: -30px; width: 120px; height: 120px; pointer-events: none; background: rgb(255 255 255 / 40%); border-radius: 50%; }
.workbench-stat-card:hover { transform: translateY(-3px); box-shadow: 0 8px 24px rgb(0 0 0 / 14%); }
.stat-label { z-index: 1; margin-bottom: 14px; font-size: 13px; line-height: 20px; opacity: .85; }
.stat-row { z-index: 1; display: flex; align-items: center; gap: 10px; }
.stat-icon { display: inline-flex; align-items: center; justify-content: center; width: 44px; height: 44px; border-radius: 12px; background: rgb(255 255 255 / 55%); }
.stat-row strong { font-size: 40px; line-height: 1; font-weight: 800; }
.stat-action { z-index: 1; margin-top: 12px; font-size: 12px; opacity: .7; }
.tone-blue { color: #0958d9; background: linear-gradient(135deg, rgb(230 244 255 / 55%) 0%, rgb(145 202 255 / 45%) 100%); border: 1px solid rgb(22 119 255 / 15%); }
.tone-green { color: #237804; background: linear-gradient(135deg, rgb(246 255 237 / 55%) 0%, rgb(183 235 143 / 45%) 100%); border: 1px solid rgb(82 196 26 / 15%); }
.tone-orange { color: #ad4e00; background: linear-gradient(135deg, rgb(255 247 230 / 55%) 0%, rgb(255 213 145 / 45%) 100%); border: 1px solid rgb(230 162 60 / 15%); }
.tone-purple { color: #531dab; background: linear-gradient(135deg, rgb(249 240 255 / 55%) 0%, rgb(211 173 247 / 45%) 100%); border: 1px solid rgb(114 46 209 / 15%); }
.tone-red { color: #a8071a; background: linear-gradient(135deg, rgb(255 241 240 / 55%) 0%, rgb(255 163 158 / 45%) 100%); border: 1px solid rgb(245 108 108 / 15%); }
.tone-cyan { color: #006d75; background: linear-gradient(135deg, rgb(230 255 251 / 55%) 0%, rgb(135 232 222 / 45%) 100%); border: 1px solid rgb(0 109 117 / 15%); }
@media (max-width: 1024px) { .workbench-stat-card { min-height: 100px; padding: 24px 20px 20px; } .stat-row strong { font-size: 32px; } }
</style>
