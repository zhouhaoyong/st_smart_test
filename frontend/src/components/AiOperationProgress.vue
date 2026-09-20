<template>
  <div class="ai-operation-loading-card" :class="{ 'is-system': kind === 'system', 'is-embedded': embedded }" role="status" aria-live="polite">
    <div class="ai-loading-card-head">
      <span v-if="showBadge" class="ai-loading-badge ai-loading-badge--breathing" :class="{ 'is-system': kind === 'system' }">
        <img class="ai-loading-brand-icon" src="/favicon.svg" alt="" aria-hidden="true">
        {{ statusLabel || (kind === 'system' ? '系统处理中' : 'AI处理中') }}
      </span>
      <div v-if="showTimer" class="ai-operation-loading-time ai-operation-loading-time--breathing" role="timer" :aria-label="timerAriaLabel">
        <el-icon class="ai-operation-loading-time-icon"><Timer /></el-icon>
        <span>{{ elapsedText }}</span>
      </div>
    </div>

    <div class="ai-loading-visual" :class="{ 'is-system': kind === 'system' }" aria-hidden="true">
      <img class="ai-loading-orbit-icon" :src="aiLoadingOrbitIcon" alt="">
    </div>

    <div class="ai-loading-copy">
      <strong class="ai-operation-loading-title">{{ title }}</strong>
      <span class="ai-operation-loading-hint">{{ hint }}</span>
    </div>

    <template v-if="showProgress">
      <div class="ai-loading-progress-heading">
        <span>实时进度</span>
        <strong>{{ normalizedPercentage }}%</strong>
      </div>
      <el-progress
        class="ai-operation-loading-bar"
        :percentage="normalizedPercentage"
        :show-text="false"
        :stroke-width="6"
      />
    </template>

    <div v-if="showProgress || metaText" class="ai-loading-progress-info">
      <span v-if="showProgress" class="ai-operation-loading-progress">{{ progressText }}</span>
      <span v-if="metaText" class="ai-operation-loading-meta">{{ metaText }}</span>
    </div>

    <div v-if="showCancel" class="ai-operation-loading-actions">
      <el-button class="ai-operation-loading-cancel" @click="emit('cancel')">{{ cancelLabel }}</el-button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Timer } from '@element-plus/icons-vue'

const aiLoadingOrbitIcon = `${import.meta.env.BASE_URL}ai-loading-orbit.svg`

const props = defineProps({
  kind: { type: String, default: 'ai' },
  statusLabel: { type: String, default: '' },
  title: { type: String, default: 'AI处理中' },
  hint: { type: String, default: '请稍候…' },
  elapsedText: { type: String, default: '00:00' },
  percentage: { type: [Number, String], default: 0 },
  progressText: { type: String, default: '' },
  metaText: { type: String, default: '' },
  timerAriaLabel: { type: String, default: '处理耗时' },
  cancelLabel: { type: String, default: '取消' },
  showBadge: { type: Boolean, default: true },
  showTimer: { type: Boolean, default: true },
  showProgress: { type: Boolean, default: true },
  showCancel: { type: Boolean, default: true },
  embedded: { type: Boolean, default: false },
})

const emit = defineEmits(['cancel'])

const normalizedPercentage = computed(() => {
  const value = Number(props.percentage)
  if (!Number.isFinite(value)) return 0
  return Math.min(100, Math.max(0, Math.round(value)))
})
</script>

<style scoped>
.ai-operation-loading-card {
  position: relative;
  width: min(100%, 640px);
  min-width: 0;
  max-width: 640px;
  padding: 40px 40px 34px;
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 16px;
  box-sizing: border-box;
  border: 1px solid var(--el-border-color-light);
  border-radius: 10px;
  background: #fff;
  box-shadow: var(--el-box-shadow);
}
.ai-loading-card-head {
  width: 100%;
  min-height: 22px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.ai-loading-badge {
  --ai-loading-badge-glow: rgba(37, 99, 235, .18);
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 9px;
  border-radius: 999px;
  background: #eff6ff;
  color: #2563eb;
  font-size: 12px;
  font-weight: 600;
}
.ai-loading-brand-icon { width: 15px; height: 15px; flex: 0 0 auto; object-fit: contain; }
.ai-loading-badge.is-system {
  --ai-loading-badge-glow: rgba(22, 163, 74, .18);
  background: #f0fdf4;
  color: #16a34a;
}
.ai-loading-badge--breathing {
  animation: ai-operation-badge-breathe 1.8s ease-in-out infinite;
  transform-origin: center;
}
@keyframes ai-operation-badge-breathe {
  0%, 100% { opacity: .78; box-shadow: 0 0 0 0 var(--ai-loading-badge-glow); transform: scale(1); }
  50% { opacity: 1; box-shadow: 0 0 0 5px transparent; transform: scale(1.015); }
}
.ai-operation-loading-time {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
  color: var(--el-color-primary);
  font-size: 16px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  line-height: 1;
}
.ai-operation-loading-time-icon { font-size: 16px; }
.ai-operation-loading-time--breathing {
  animation: ai-operation-time-breathe 1.6s ease-in-out infinite;
  transform-origin: right center;
}
@keyframes ai-operation-time-breathe {
  0%, 100% { opacity: .72; transform: scale(1); text-shadow: 0 0 0 rgba(64, 158, 255, 0); }
  50% { opacity: 1; transform: scale(1.06); text-shadow: 0 0 10px rgba(64, 158, 255, .28); }
}
.ai-loading-visual { width: 92px; height: 92px; align-self: center; margin: 2px auto 0; }
.ai-loading-orbit-icon { display: block; width: 100%; height: 100%; object-fit: contain; }
.ai-loading-copy { display: flex; flex: 0 0 auto; flex-direction: column; align-items: center; gap: 8px; text-align: center; }
.ai-operation-loading-title { color: var(--el-text-color-primary); font-size: 19px; line-height: 1.35; }
.ai-operation-loading-hint { display: block; flex: 0 0 auto; color: #64748b; font-size: 13px; line-height: 1.5; }
.ai-loading-progress-heading { display: flex; align-items: center; justify-content: space-between; gap: 12px; color: #64748b; font-size: 12px; }
.ai-loading-progress-heading strong { color: #2563eb; font-size: 14px; font-variant-numeric: tabular-nums; }
.ai-operation-loading-bar { width: 100%; margin: 0; }
.ai-operation-loading-bar :deep(.el-progress-bar__outer) { background: #dbeafe; }
.ai-loading-progress-info {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 10px 14px;
  box-sizing: border-box;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
  background: var(--el-fill-color-lighter);
}
.ai-operation-loading-progress,
.ai-operation-loading-meta {
  min-width: 0;
  overflow-wrap: anywhere;
  white-space: normal;
}
.ai-operation-loading-progress { color: #334155; font-size: 13px; font-weight: 600; line-height: 1.4; }
.ai-operation-loading-meta { color: #64748b; font-size: 12px; line-height: 1.45; }
.ai-operation-loading-actions {
  width: 100%;
  margin-top: 12px;
  padding-top: 14px;
  display: flex;
  justify-content: center;
  border-top: 1px solid var(--el-border-color-lighter);
}
.ai-operation-loading-cancel { min-width: 120px; }
.ai-operation-loading-card.is-embedded {
  width: 100%;
  max-width: none;
  padding: 12px 4px 8px;
  border: 0;
  border-radius: 0;
  background: transparent;
  box-shadow: none;
}
.ai-operation-loading-card.is-embedded .ai-loading-visual { margin-top: 0; }
@media (prefers-reduced-motion: reduce) {
  .ai-operation-loading-time--breathing,
  .ai-loading-badge--breathing { animation-play-state: paused; }
}
@media (max-width: 640px) {
  .ai-operation-loading-card {
    width: calc(100% - 16px);
    max-width: calc(100% - 16px);
    padding: 24px 20px 16px;
    gap: 8px;
  }
}
</style>
