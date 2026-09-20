<template>
  <div class="import-table-state" :class="{ 'is-compact': compact }">
    <template v-if="error">
      <el-icon class="import-table-state-icon"><CircleCloseFilled /></el-icon>
      <span class="import-table-state-message">{{ error }}</span>
      <el-button type="primary" link size="small" @click="$emit('retry')">重新加载</el-button>
    </template>
    <el-empty v-else :description="emptyText" :image-size="64" />
  </div>
</template>

<script setup>
import { CircleCloseFilled } from '@element-plus/icons-vue'

defineProps({
  emptyText: { type: String, default: '暂无数据' },
  error: { type: String, default: '' },
  compact: Boolean,
})

defineEmits(['retry'])
</script>

<style scoped>
.import-table-state {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 120px;
  padding: 16px;
  color: var(--el-text-color-secondary);
}
.import-table-state-icon {
  color: var(--el-color-danger);
  font-size: 18px;
}
.import-table-state.is-compact {
  justify-content: flex-start;
  min-height: 0;
  padding: 0;
}
.import-table-state-message {
  max-width: min(560px, 80%);
  line-height: 20px;
  text-align: center;
}
</style>
