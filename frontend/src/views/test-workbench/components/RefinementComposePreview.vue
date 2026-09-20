<template>
  <el-dialog v-model="visible" :title="title" width="820px" top="8vh" append-to-body class="compose-preview-dialog">
    <div class="compose-preview">
      <el-tabs v-model="tab" class="compose-tabs">
        <el-tab-pane :label="originalLabel" name="original">
          <pre class="preview-pre">{{ original || emptyOriginal }}</pre>
        </el-tab-pane>
        <el-tab-pane :label="composedLabel" name="composed">
          <pre class="preview-pre" :class="{ 'is-placeholder': !composed }">{{ composed || emptyComposed }}</pre>
        </el-tab-pane>
      </el-tabs>
    </div>
  </el-dialog>
</template>

<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  modelValue: Boolean,
  title: { type: String, default: '正文预览' },
  original: { type: String, default: '' },
  composed: { type: String, default: '' },
  originalLabel: { type: String, default: '原始输入' },
  composedLabel: { type: String, default: '补全正文' },
  emptyOriginal: { type: String, default: '暂无原始输入' },
  emptyComposed: { type: String, default: '暂未生成正文' },
})
const emit = defineEmits(['update:modelValue'])
const visible = computed({ get: () => props.modelValue, set: value => emit('update:modelValue', value) })
const tab = ref('composed')
</script>

<style scoped>
.compose-tabs :deep(.el-tabs__header) {
  margin-bottom: 8px;
}
.preview-pre {
  height: min(520px, 58vh);
  margin: 0;
  padding: 12px;
  overflow: auto;
  white-space: pre-wrap;
  color: var(--el-text-color-primary);
  background: var(--el-fill-color-light);
  border-radius: 6px;
  font: 13px/1.7 ui-monospace, SFMono-Regular, Menlo, monospace;
}
.preview-pre.is-placeholder {
  color: var(--el-text-color-placeholder);
}
</style>
