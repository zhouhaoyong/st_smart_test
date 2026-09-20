<template>
  <el-tabs v-model="tab" class="detail-tabs">
    <el-tab-pane label="响应体" name="body">
      <slot name="body" :text="bodyText">
        <pre class="code-block">{{ bodyText || '(无)' }}</pre>
      </slot>
    </el-tab-pane>
    <el-tab-pane label="响应头" name="headers">
      <slot name="headers" :text="headersText">
        <pre class="code-block">{{ headersText || '(无)' }}</pre>
      </slot>
    </el-tab-pane>
  </el-tabs>
</template>

<script setup>
import { computed } from 'vue'

// 响应体、响应头恒定展示（无数据时显示「(无)」），
// 保证调试、运行结果、测试报告的页签结构完全一致，不因数据有无而变化
const props = defineProps({
  activeTab: { type: String, default: 'body' },
  bodyText: { type: String, default: '' },
  headersText: { type: String, default: '' },
})

const emit = defineEmits(['update:activeTab'])

const tab = computed({
  get: () => props.activeTab,
  set: value => emit('update:activeTab', value),
})
</script>

<style scoped>
.detail-tabs :deep(.el-tabs__content) { padding-top: 8px; }
.detail-tabs :deep(.el-tab-pane) { min-height: 0; }
.code-block {
  max-height: min(360px, 36vh);
  overflow: auto;
  margin: 0;
  padding: 10px;
  border-radius: 6px;
  background: #f7f9fc;
  font-family: SFMono-Regular, Consolas, monospace;
  font-size: 13px;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
