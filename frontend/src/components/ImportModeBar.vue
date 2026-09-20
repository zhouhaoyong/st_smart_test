<template>
  <div class="mode-bar">
    <span class="mode-bar-label">导入模式</span>
    <el-radio-group
      :model-value="modelValue"
      size="default"
      aria-label="导入模式"
      @update:model-value="$emit('update:modelValue', $event)"
    >
      <el-radio-button value="full" :disabled="loading">全量模式</el-radio-button>
      <el-radio-button value="incremental" :disabled="loading">增量模式</el-radio-button>
    </el-radio-group>
    <el-tooltip placement="bottom-start" popper-class="import-mode-tooltip">
      <template #content>
        <div class="mode-tip-line" v-for="line in importModeTips" :key="line">{{ line }}</div>
      </template>
      <el-icon class="mode-bar-help"><QuestionFilled /></el-icon>
    </el-tooltip>
    <div v-if="stats?.length" class="mode-bar-stats">
      <el-tag
        v-for="stat in stats"
        :key="stat.key"
        :type="stat.tagType"
        effect="light"
        size="small"
        class="mode-stat-tag"
      >{{ stat.label }} {{ stat.value }}</el-tag>
    </div>
  </div>
</template>

<script setup>
import { QuestionFilled } from '@element-plus/icons-vue'
import { IMPORT_MODE_TIPS } from '@/utils/interfaceCollections'

const importModeTips = IMPORT_MODE_TIPS

defineProps({
  modelValue: { type: String, default: 'full' },
  loading: Boolean,
  stats: { type: Array, default: () => [] },
})

defineEmits(['update:modelValue'])
</script>

<style scoped>
.mode-bar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px 12px;
  min-width: 0;
}
.mode-bar-label { color: var(--el-text-color-regular); font-size: 14px; line-height: 20px; }
.mode-bar-help { color: var(--el-text-color-secondary); font-size: 15px; cursor: help; }
.mode-bar-help:hover { color: var(--el-color-primary); }
.mode-bar :deep(.el-radio-button + .el-radio-button) { margin-left: -1px; }
.mode-bar :deep(.el-radio-button__inner) {
  border: 1px solid var(--el-border-color);
  outline: none;
  box-shadow: none !important;
}
.mode-bar :deep(.el-radio-button.is-active) { z-index: 1; }
.mode-bar :deep(.el-radio-button.is-active .el-radio-button__inner) {
  border-color: var(--el-color-primary);
}
.mode-bar-stats {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px 16px;
  margin-left: auto;
  min-width: 0;
}
.mode-stat-tag {
  font-weight: 500;
  line-height: 22px;
  padding: 0 8px;
  transition: none;
}
.mode-stat-tag:hover { transform: none; }
@media (max-width: 720px) {
  .mode-bar-stats { margin-left: 0; }
}
</style>

<style>
.import-mode-tooltip { max-width: 420px; line-height: 1.7; }
.import-mode-tooltip .mode-tip-line + .mode-tip-line { margin-top: 4px; }

/* 两个导入弹窗共用同一套外壳：正文不带整窗滚动，列表自己占据滚动区域。 */
.import-dialog-shell {
  display: flex;
  flex-direction: column;
  max-height: min(92vh, 920px);
}
.import-dialog-shell--preview { height: min(92vh, 920px); }
.import-dialog-shell--compact { height: auto; }
.import-dialog-shell .el-dialog__header,
.import-dialog-shell .el-dialog__footer { flex-shrink: 0; }
.import-dialog-shell .el-dialog__body {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  padding: 20px 28px;
}
.import-dialog-shell .import-dialog-body,
.import-dialog-shell .ai-import-body {
  height: 100%;
  min-height: 0;
  overflow-y: auto;
}
.import-dialog-shell .import-dialog-body--preview,
.import-dialog-shell .ai-import-body--preview { overflow: hidden; }
.import-dialog-shell--compact .el-dialog__body { flex: 0 1 auto; overflow: visible; }
.import-dialog-shell--compact .import-dialog-body,
.import-dialog-shell--compact .ai-import-body { height: auto; overflow: visible; }
.import-dialog-shell--result .el-dialog__body { flex: 0 1 auto; overflow: visible; }
.import-dialog-shell--result .import-dialog-body { height: auto; min-height: 0; overflow: visible; }
.import-dialog-shell .import-table-scroll {
  width: 100%;
  min-width: 0;
}
.import-dialog-shell .import-table-scroll .el-table__inner-wrapper { min-width: 100%; }
</style>
