<template>
  <el-dialog
    v-model="visible"
    :title="title"
    width="92vw"
    top="7vh"
    append-to-body
    destroy-on-close
    :close-on-click-modal="false"
    :before-close="handleBeforeClose"
    class="requirement-ai-dialog"
  >
    <div v-loading="loading" class="ai-refinement" :class="{ 'is-start-confirm': !conversationStarted }">
      <!-- 所有 AI 流程均先确认本次模型，再触发第一轮模型调用。
           一旦发起过调用就不再回到本页：首轮失败时 session 仍为 null，
           退回确认页会把模型报错气泡整块吞掉，用户看不到失败原因。 -->
      <RefinementStartConfirm
        v-if="!conversationStarted"
        :model-info="modelInfo"
        :model-candidates="modelCandidates"
        :selected-model-id="selectedModelId"
        :model-load-error="modelLoadError"
        :can-start="canStart"
        :title="workflow.startTitle"
        :description="workflow.startDescription"
        :start-label="workflow.startActionLabel"
        :cancel-label="workflow.startCancelLabel"
        :rule-title="workflow.ruleTitle"
        :rule-text="workflow.ruleText"
        :usage-text="workflow.usageText"
        :show-title-input="isMergeConversation"
        :title-input="mergeTitle"
        @cancel="visible = false"
        @start="start"
        @update:title-input="mergeTitle = $event"
        @update:selected-model-id="selectModel($event)"
      />

      <!-- 会话页：展示本次补全会话中的用户输入与 AI 回复（每次打开重新开始，不回放历史会话） -->
      <template v-else>
        <AiConversationFrame>
          <div class="ai-status">
          <el-tag class="ai-status-tag" :type="statusType" effect="light" size="small" round>
            <span v-if="streaming" class="status-dot" />{{ statusLabel }}
          </el-tag>
          <span class="ai-status-hint">{{ workflow.sessionHint }}</span>
          </div>

          <div class="conversation-wrap">
          <el-scrollbar ref="scrollRef" class="conversation-body" @scroll="onScroll">
            <RefinementMessageCard
              v-for="(message, index) in messages"
              :key="message.id"
              :message="message"
              :copyable="messageCopyable(message, index)"
              :supports-reasoning="!!modelInfo?.supports_reasoning"
              :active-action-id="composeMsgId"
              :end-action-id="endActionMsgId"
              :end-label="workflow.endActionLabel"
              :end-loading="composing"
              :merge-mode="workflow.mergeMode"
              :active-question-id="activeQuestionMsgId"
              :answer-draft="answerDraft"
              :can-submit="canSend"
              :can-end="canEnd"
              :retry-selection-required="retrySelectionRequired"
              :retry-model-loading="retryModelLoading"
              :is-latest-message="index === messages.length - 1"
              @copy="copyText"
              @preview="saveVisible = true"
              @compare="compare"
          @comparison-preview="comparisonDialog = { visible: true, result: $event }"
              @case-preview="openTestCasePreview"
              @end="endConversation"
              @answer-change="onAnswerChange"
              @submit="send"
              @supplement="sendSupplement"
              @retry-open="refreshRetryCandidates"
              @retry="retry"
            />

            <el-empty
              v-if="!messages.length && !streaming"
              description="点击开始后，AI 才会发起第一次补全调用"
              :image-size="72"
            />
          </el-scrollbar>

          <div v-show="messages.length" class="scroll-nav-actions">
            <el-button
              v-show="!stickTop"
              class="scroll-nav-btn"
              circle
              :icon="ArrowUp"
              aria-label="回到顶部"
              @click="scrollToTopManually"
            />
            <el-button
              v-show="!stickBottom"
              class="scroll-nav-btn"
              circle
              :icon="ArrowDown"
              aria-label="回到底部"
              @click="scrollToBottomManually"
            />
          </div>
          </div>
        </AiConversationFrame>

        <div v-if="streaming" class="stream-action-bar">
          <AiStopStreamButton @confirm="stopStream" />
        </div>

        <RefinementSaveDialog
          v-if="!isPreflightConversation"
          v-model="saveVisible"
          :source="composedDraft"
          :original="originalContent"
          :check="composeCheck"
          :title="workflow.saveTitle"
          :asset-title="workflow.assetTitle"
          :title-editable="workflow.titleEditable"
          :title-label="workflow.titleLabel"
          :title-max-length="workflow.titleMaxLength"
          :saving="saving"
          @save="save"
          @copy="copyText"
        />
        <RequirementComparisonDialog
          v-model="comparisonDialog.visible"
          :merge-mode="isMergeConversation"
          :original="originalContent"
          :sources="props.scope?.source_snapshots || []"
          :result="composedDraft"
          :comparison="comparisonDialog.result"
          @preview-save="openSaveFromComparison"
        />

        <!-- 额度提示条：原「补充说明」输入框已下线，作答与终态动作全部收敛到问题卡片内。 -->
        <p v-if="!conversationBroken && workflow.actionHint" class="ai-quota-tip">{{ workflow.actionHint }}</p>
      </template>
    </div>
  </el-dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { ArrowDown, ArrowUp } from '@element-plus/icons-vue'
import RefinementStartConfirm from './RefinementStartConfirm.vue'
import RefinementMessageCard from './RefinementMessageCard.vue'
import AiConversationFrame from './AiConversationFrame.vue'
import RefinementSaveDialog from './RefinementSaveDialog.vue'
import RequirementComparisonDialog from './RequirementComparisonDialog.vue'
import AiStopStreamButton from './AiStopStreamButton.vue'
import { useRequirementRefinement } from '../composables/useRequirementRefinement.js'

const props = defineProps({
  modelValue: Boolean,
  requirement: { type: Object, default: null },
  // 标题与接口适配器：默认对接单条需求；合并需求复用同一弹窗时传入自身配置
  title: { type: String, default: 'AI 补全需求' },
  api: { type: Object, default: null },
  // 通用对话框的场景文案；后续 AI 对话可复用同一壳层并传入自己的动作名称和标签。
  workflow: { type: Object, default: () => ({}) },
  // 「对话式合并」场景：保存前没有资产，作用域 { version_id, source_type, source_ids, title }
  // 随每次请求回传，后端据此重读来源需求正文。对已有资产补全时为 null。
  scope: { type: Object, default: null },
})
const emit = defineEmits(['update:modelValue', 'previewed', 'preflight-complete', 'case-preview'])

const visible = computed({
  get: () => props.modelValue,
  set: value => emit('update:modelValue', value),
})
const saveVisible = ref(false)
const mergeTitle = ref('')
const comparisonDialog = ref({ visible: false, result: null })
const openSaveFromComparison = () => {
  comparisonDialog.value.visible = false
  saveVisible.value = true
}
const isMergeConversation = computed(() => props.workflow.mode === 'merge' || (!props.workflow.mode && !!props.scope))
const isPreflightConversation = computed(() => props.workflow.mode === 'test_case')
const workflow = computed(() => {
  const isMergeConversation = props.workflow.mode === 'merge' || (!props.workflow.mode && !!props.scope)
  const isPreflightConversation = props.workflow.mode === 'test_case'
  const defaults = isMergeConversation
    ? {
        startTitle: '开始 AI 合并需求',
        startDescription: '先确认来源间的差异与遗漏，再由 AI 整理为一份完整的合并需求。',
        startActionLabel: '开始 AI 合并',
        startCancelLabel: '暂不合并',
        ruleTitle: '合并规则',
        ruleText: '优先澄清冲突、重复和缺口；后续仅追问影响合并结论的关键问题，最多 3 轮。',
        usageText: '开始、每轮作答和整理结果各调用 1 次 AI；预览、保存不调用 AI。',
        saveTitle: '预览并保存合并需求',
        endActionLabel: '结束对话并整理合并需求',
        mergeMode: true,
        assetLabel: '合并需求正文',
        titleEditable: true,
        titleLabel: '需求标题',
        titleMaxLength: 20,
        sessionHint: '本次对话仅在当前窗口保留；保存后新增一条待确认的合并需求，来源需求不会被修改。',
        actionHint: '每提交一组回答调用 1 次 AI；开始合并和整理结果各调用 1 次。预览、保存不调用 AI。',
      }
    : isPreflightConversation
      ? {
          startTitle: '开始 AI 生成对话',
          startDescription: 'AI 会先集中确认影响测试范围、测试点、步骤和预期结果的关键疑点，再开始生成用例。',
          startActionLabel: '开始生成对话',
          startCancelLabel: '暂不生成',
          ruleTitle: '生成规则',
          ruleText: '首轮尽可能一次问全关键疑点；已明确内容直接用于生成，不会要求逐条确认测试点。',
          usageText: '开始对话调用 1 次 AI；确认完成后才可生成用例。',
          endActionLabel: '确认并开始生成测试用例',
          mergeMode: false,
          sessionHint: '本次生成对话仅用于生成测试用例，不会保存中间需求或测试点资产。',
          actionHint: '请在本轮集中确认关键疑点；跳过的内容不会被当作业务规则或确定预期。',
        }
      : {
        startTitle: '开始 AI 补全需求',
        startDescription: '先补齐影响实现和验收的关键信息，再由 AI 整理为需求正文。',
        startActionLabel: '开始 AI 补全',
        startCancelLabel: '暂不补全',
        ruleTitle: '追问规则',
        ruleText: '优先确认流程、权限和异常；后续仅追问影响实现的关键问题，通常在 3 轮内完成。',
        usageText: '开始、每轮作答和整理正文各调用 1 次 AI；预览、保存不调用 AI。',
        saveTitle: '预览并保存补全正文',
        endActionLabel: '结束对话并补全需求',
        mergeMode: false,
        assetLabel: '补全正文',
        sessionHint: '本次对话仅在当前窗口保留；保存后新增一条待确认的 AI 补全需求，原始需求不会被修改。',
        actionHint: '每提交一组回答调用 1 次 AI；开始补全和整理正文各调用 1 次。预览、保存不调用 AI。',
      }
  return { ...defaults, ...props.workflow }
})

const {
  loading,
  streaming,
  composing,
  saving,
  conversationStarted,
  conversationBroken,
  modelInfo,
  modelCandidates,
  selectedModelId,
  modelLoadError,
  messages,
  scrollRef,
  statusType,
  statusLabel,
  canStart,
  canEnd,
  canSend,
  retrySelectionRequired,
  retryModelLoading,
  stickBottom,
  stickTop,
  originalContent,
  composedDraft,
  composeCheck,
  composeMsgId,
  endActionMsgId,
  activeQuestionMsgId,
  answerDraft,
  onAnswerChange,
  selectModel,
  scrollToTopManually,
  scrollToBottomManually,
  onScroll,
  copyText,
  messageCopyable,
  start,
  send,
  sendSupplement,
  retry,
  refreshRetryCandidates,
  stopStream,
  endConversation,
  compare,
  openTestCasePreview,
  save,
  handleBeforeClose,
  open,
} = useRequirementRefinement({
  getRequirement: () => props.requirement,
  close: () => { visible.value = false },
  emit,
  api: props.api,
  getScope: () => props.scope ? { ...props.scope, title: mergeTitle.value.trim() || undefined } : null,
})

watch(visible, async isOpen => {
  if (!isOpen) return
  saveVisible.value = false
  comparisonDialog.value = { visible: false, result: null }
  mergeTitle.value = props.scope?.title || ''
  await open()
})
</script>

<style scoped>
/* 宽度 92vw 自适应；对话流+追问卡片再宽就不利于阅读，故 max-width 比需求预览弹窗收得更紧。
   用 :global 是因为 el-dialog append-to-body 后根节点是 teleport，scoped 属性不一定落到 .el-dialog 上。 */
:global(.requirement-ai-dialog) { max-width: 1200px; }

.ai-refinement {
  height: min(690px, 72vh);
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.ai-refinement.is-start-confirm {
  height: auto;
}
.ai-refinement.is-start-confirm :deep(.start-confirm) {
  flex: none;
}
/* 顶部状态条：短状态标签，永不被长文本撑破 */
.ai-status {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 30px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
.ai-status-tag {
  max-width: 60%;
}
.ai-status-tag :deep(.el-tag__content) {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ai-status-hint {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
/* 额度提示条：替代原输入框底部提示，贴合对话区底边 */
.ai-quota-tip {
  flex-shrink: 0;
  margin: 0;
  padding-top: 10px;
  border-top: 1px solid var(--el-border-color-lighter);
  color: var(--el-text-color-secondary);
  font-size: 12px;
  line-height: 1.6;
}
.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
  animation: pulse 1s ease-in-out infinite;
}

/* 会话区 */
.conversation-wrap {
  position: relative;
  flex: 1;
  min-height: 0;
  display: flex;
}
.conversation-body {
  flex: 1;
  min-height: 0;
  padding-right: 6px;
}
.stream-action-bar {
  display: flex;
  flex-shrink: 0;
  width: 42px;
  margin-left: auto;
  justify-content: center;
  min-height: 50px;
  padding: 6px 0;
}
.scroll-nav-actions {
  position: absolute;
  right: 0;
  bottom: 14px;
  z-index: 5;
  display: flex;
  align-items: center;
  width: 42px;
  flex-direction: column;
  gap: 8px;
}
.scroll-nav-btn {
  width: 34px;
  height: 34px;
  margin-left: 0;
  padding: 0;
  font-size: 16px;
  color: var(--el-color-primary);
  background: var(--el-bg-color);
  border-color: var(--el-color-primary-light-7);
  box-shadow: 0 2px 10px var(--el-color-primary-light-8);
}

@keyframes pulse {
  50% {
    opacity: 0.3;
    transform: scale(0.75);
  }
}
</style>
