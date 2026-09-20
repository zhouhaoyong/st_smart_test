<template>
  <div class="answer-box">
    <div class="answer-composer" :class="{ 'is-streaming': streaming }">
      <el-input
        class="answer-textarea"
        :model-value="modelValue"
        type="textarea"
        :autosize="{ minRows: 2, maxRows: 5 }"
        resize="none"
        placeholder="补充说明（可选）：可补充新的规则、交互或异常场景；逐题作答请在上方问题卡片中选择"
        :disabled="streaming"
        @update:model-value="emit('update:modelValue', $event)"
      />

      <div class="composer-toolbar">
        <div class="workflow-actions">
          <el-tooltip v-for="action in actionItems" :key="action.key" :content="action.tooltip" placement="top">
            <el-button
              text
              class="composer-action"
              :icon="action.icon"
              :loading="action.loading"
              :disabled="action.disabled"
              @click="emit('action', action.key)"
            >
              {{ action.label }}
            </el-button>
          </el-tooltip>
        </div>

        <el-tooltip v-if="!streaming" content="提交回答" placement="top">
          <el-button
            class="composer-submit"
            type="primary"
            circle
            :icon="Promotion"
            :disabled="!canSend"
            @click="emit('send')"
          />
        </el-tooltip>
        <AiStopStreamButton v-else @confirm="emit('stop')" />
      </div>
    </div>

    <p v-if="actionHint" class="quota-tip">{{ actionHint }}</p>
  </div>
</template>

<script setup>
import { Promotion } from '@element-plus/icons-vue'
import AiStopStreamButton from './AiStopStreamButton.vue'

defineProps({
  modelValue: { type: String, default: '' },
  streaming: Boolean,
  canSend: Boolean,
  actionItems: { type: Array, default: () => [] },
  actionHint: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue', 'action', 'send', 'stop'])
</script>

<style scoped>
/* 回答区 */
.answer-box {
  flex-shrink: 0;
  padding-top: 12px;
  border-top: 1px solid var(--el-border-color-lighter);
}
.answer-composer {
  overflow: hidden;
  border: 1px solid var(--el-border-color);
  border-radius: 14px;
  background: var(--el-fill-color-light);
  transition: border-color 0.2s, box-shadow 0.2s;
}
.answer-composer:focus-within {
  border-color: var(--el-color-primary);
  box-shadow: 0 0 0 3px var(--el-color-primary-light-9);
}
.answer-composer.is-streaming {
  border-color: var(--el-color-danger-light-5);
}
.answer-textarea :deep(.el-textarea__inner) {
  padding: 12px 14px 6px;
  border: 0;
  border-radius: 0;
  background: transparent;
  box-shadow: none;
}
.answer-textarea :deep(.el-textarea__inner:focus) {
  box-shadow: none;
}
.composer-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 6px 10px 10px;
}
.workflow-actions {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 8px;
  /* 只有单个动作按钮（结束对话并补全需求），不需要滚动容器。
     注意：overflow-x: auto 会让 overflow-y 从 visible 被计算成 auto，
     导致按钮 loading 时高出行盒 1px 就冒出上下+左右滚动条，故用 wrap 兜底、不滚动。 */
  flex-wrap: wrap;
}
.composer-action {
  flex: none;
  margin: 0;
  padding: 4px 6px;
}
.composer-submit {
  flex: none;
  width: 32px;
  height: 32px;
  padding: 0;
}
.quota-tip {
  margin: 8px 0 0;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  line-height: 1.6;
}
</style>
