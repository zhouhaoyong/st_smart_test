<template>
  <el-tooltip content="停止生成" placement="top">
    <button class="ai-stop-stream-button" type="button" aria-label="停止生成" @click="confirmStop">
      <span class="ai-stop-stream-button__icon" />
    </button>
  </el-tooltip>
</template>

<script setup>
import { ElMessageBox } from 'element-plus'

const emit = defineEmits(['confirm'])

async function confirmStop() {
  try {
    await ElMessageBox.confirm('停止后，本轮 AI 生成结果不会被采纳。', '停止生成', {
      type: 'warning',
      confirmButtonText: '停止生成',
      cancelButtonText: '继续生成',
    })
    emit('confirm')
  } catch {
  }
}
</script>

<style scoped>
.ai-stop-stream-button {
  position: relative;
  z-index: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 38px;
  height: 38px;
  padding: 0;
  color: #fff;
  cursor: pointer;
  border: 0;
  border-radius: 50%;
  background: linear-gradient(135deg, #f78989, #f56c6c);
  box-shadow: 0 5px 14px rgb(245 108 108 / 38%);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.ai-stop-stream-button::before {
  position: absolute;
  z-index: -1;
  inset: -5px;
  border: 1px solid rgb(245 108 108 / 58%);
  border-radius: inherit;
  content: '';
  animation: stop-breathe 1.7s ease-out infinite;
}
.ai-stop-stream-button:hover,
.ai-stop-stream-button:focus-visible {
  outline: none;
  transform: scale(1.06);
  box-shadow: 0 7px 18px rgb(245 108 108 / 48%);
}
.ai-stop-stream-button__icon {
  width: 11px;
  height: 11px;
  border-radius: 2px;
  background: currentColor;
}
@keyframes stop-breathe {
  0%, 100% {
    opacity: 0.62;
    transform: scale(0.88);
  }
  58% {
    opacity: 0;
    transform: scale(1.26);
  }
}
@media (prefers-reduced-motion: reduce) {
  .ai-stop-stream-button::before { animation: none; }
}
</style>
