<template>
  <section class="start-confirm">
    <div class="start-icon"><el-icon><MagicStick /></el-icon></div>
    <h3>{{ title }}</h3>
    <p>{{ description }}</p>

    <div class="start-rules">
      <div class="rule-card rule-card-primary">
        <div class="rule-title">{{ ruleTitle }}</div>
        <p>{{ ruleText }}</p>
      </div>
      <div class="rule-card">
        <div class="rule-title">调用与统计</div>
        <p>{{ usageText }}</p>
      </div>
    </div>

    <div v-if="showTitleInput" class="start-title-input">
      <span>{{ titleInputLabel }}</span>
      <el-input
        :model-value="titleInput"
        maxlength="100"
        show-word-limit
        :placeholder="titleInputPlaceholder"
        @update:model-value="emit('update:titleInput', $event)"
      />
    </div>

    <AiModelSelectionPanel
      :model-info="modelInfo"
      :model-candidates="modelCandidates"
      :selected-model-id="selectedModelId"
      :disable-single="false"
      @update:selected-model-id="emit('update:selectedModelId', $event)"
    />

    <el-alert
      v-if="modelLoadError"
      type="warning"
      :closable="false"
      show-icon
    >
      <template #title>
        <div class="model-load-error">
          <span>{{ modelLoadError }}</span>
          <el-button link type="primary" @click="openModelConfig">去配置</el-button>
        </div>
      </template>
    </el-alert>

    <div class="start-actions">
      <el-button @click="emit('cancel')">{{ cancelLabel }}</el-button>
      <el-button type="primary" :disabled="!canStart" @click="emit('start')">{{ startLabel }}</el-button>
    </div>
  </section>
</template>

<script setup>
import { MagicStick } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import AiModelSelectionPanel from './AiModelSelectionPanel.vue'

const router = useRouter()
const openModelConfig = () => {
  const target = router.resolve({ name: 'ModelAdminModelsMine' })
  window.open(target.href, '_blank', 'noopener,noreferrer')
}

const props = defineProps({
  modelInfo: { type: Object, default: null },
  modelCandidates: { type: Array, default: () => [] },
  selectedModelId: { type: Number, default: null },
  modelLoadError: { type: String, default: '' },
  canStart: Boolean,
  title: { type: String, default: '开始 AI 补全需求' },
  description: { type: String, default: '先确认关键规则，再由 AI 整理为可保存的需求正文。' },
  startLabel: { type: String, default: '开始 AI 补全' },
  cancelLabel: { type: String, default: '暂不补全' },
  ruleTitle: { type: String, default: '追问规则' },
  ruleText: { type: String, default: '首轮集中覆盖流程、权限和异常；后续只追问影响实现的关键点，通常在 3 轮内完成。' },
  usageText: { type: String, default: '开始、提交回答和整理正文各调用 1 次；每轮回复展示本轮输入、输出、缓存和耗时。' },
  showTitleInput: Boolean,
  titleInput: { type: String, default: '' },
  titleInputLabel: { type: String, default: '合并需求标题' },
  titleInputPlaceholder: { type: String, default: '可选，留空由 AI 拟定' },
})
const emit = defineEmits(['cancel', 'start', 'update:titleInput', 'update:selectedModelId'])

</script>

<style scoped>
/* 开始确认页 */
.start-confirm {
  display: flex;
  flex: 1;
  flex-direction: column;
  align-items: center;
  justify-content: flex-start;
  overflow: auto;
  padding: 28px 64px 24px;
  text-align: center;
}
.start-icon {
  width: 48px;
  height: 48px;
  display: grid;
  place-items: center;
  border-radius: 16px;
  background: linear-gradient(135deg, var(--el-color-primary), var(--el-color-primary-light-3));
  color: #fff;
  font-size: 23px;
}
.start-confirm h3 {
  margin: 12px 0 4px;
  color: var(--el-text-color-primary);
  font-size: 20px;
}
.start-confirm > p {
  max-width: 640px;
  margin: 0;
  color: var(--el-text-color-regular);
  font-size: 14px;
  line-height: 1.6;
}
.start-rules {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  width: 100%;
  margin-top: 16px;
  text-align: left;
}
.rule-card {
  min-height: 0;
  padding: 10px 12px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  background: var(--el-fill-color-lighter);
}
.rule-card-primary {
  border-color: var(--el-color-primary-light-8);
  background: var(--el-color-primary-light-9);
}
.rule-title {
  margin-bottom: 4px;
  color: var(--el-text-color-primary);
  font-size: 13px;
  font-weight: 600;
}
.rule-title::before {
  display: inline-block;
  width: 4px;
  height: 14px;
  margin-right: 7px;
  border-radius: 2px;
  background: var(--el-color-primary);
  vertical-align: -2px;
  content: '';
}
.rule-card p {
  margin: 0;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  line-height: 1.5;
}
.start-title-input {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  margin-top: 12px;
  text-align: left;
}
.start-title-input > span {
  flex: none;
  color: var(--el-text-color-regular);
  font-size: 14px;
}
.start-confirm :deep(.el-alert) {
  margin-top: 10px;
  text-align: left;
}
.start-confirm :deep(.model-selection-panel) {
  margin-top: 12px;
}
.model-load-error {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
}
.model-load-error span {
  min-width: 0;
  line-height: 1.6;
}
.model-load-error :deep(.el-button) {
  flex-shrink: 0;
}
.start-actions {
  display: flex;
  justify-content: center;
  gap: 10px;
  margin-top: 16px;
}
@media (max-width: 720px) {
  .start-confirm { padding: 24px 24px 20px; }
  .start-rules { grid-template-columns: 1fr; }
}
</style>
