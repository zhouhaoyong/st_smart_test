<template>
  <div class="code-section">
    <div class="code-header">
      <CopyButton
        :value="content"
        label="复制"
        tooltip="复制内容"
        :disabled="copyDisabled || !content"
      />
    </div>
    <pre class="code-block">{{ content || '(无)' }}</pre>
  </div>
</template>

<script setup>
import CopyButton from '@/components/CopyButton.vue'

defineProps({
  content: { type: String, default: '' },
  copyDisabled: { type: Boolean, default: false },
})
</script>

<style scoped>
.code-header {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  margin-bottom: 4px;
}
.code-block {
  max-height: 320px;
  overflow: auto;
  margin: 0;
  padding: 12px;
  border-radius: 4px;
  background: #f5f7fa;
  font-family: SFMono-Regular, Consolas, Monaco, monospace;
  font-size: 13px;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
