<template>
  <div class="import-result-summary">
    <div class="import-result-stats">
      <div v-for="stat in stats" :key="stat.key" class="import-result-stat">
        <span>{{ stat.label }}</span>
        <div class="import-result-value">
          <strong>{{ stat.value }}</strong>
          <small>{{ stat.unit || '个' }}</small>
        </div>
      </div>
    </div>
    <div v-if="$slots.default" class="import-result-notes">
      <slot />
    </div>
  </div>
</template>

<script setup>
defineProps({
  stats: { type: Array, default: () => [] },
})
</script>

<style scoped>
.import-result-summary {
  display: flex;
  flex-direction: column;
  gap: 14px;
  width: min(100%, 820px);
  max-width: 820px;
  margin: 0 auto;
  min-width: 0;
}
.import-result-stats {
  display: grid;
  grid-template-columns: repeat(5, minmax(112px, 1fr));
  gap: 12px;
  width: 100%;
}
.import-result-stat {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
  min-width: 0;
  min-height: 82px;
  box-sizing: border-box;
  padding: 14px 16px;
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  background: var(--el-fill-color-lighter);
}
.import-result-stat span,
.import-result-stat small { color: var(--el-text-color-secondary); font-size: 13px; }
.import-result-stat strong {
  color: var(--el-color-primary);
  font-size: 24px;
  line-height: 1.1;
  font-variant-numeric: tabular-nums;
}
.import-result-value { display: flex; align-items: baseline; gap: 4px; white-space: nowrap; }
.import-result-notes { color: var(--el-text-color-secondary); font-size: 13px; line-height: 1.7; }

@media (max-width: 900px) {
  .import-result-stats { grid-template-columns: repeat(3, minmax(0, 1fr)); }
}

@media (max-width: 600px) {
  .import-result-stats { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
</style>
