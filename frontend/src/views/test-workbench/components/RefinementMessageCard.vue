<template>
  <article class="message-card" :class="[message.role, { error: message.error }]">
    <!-- 顶部标题整行可点：用户气泡=全部展开/收起，助手气泡=收起/展开正文；内部按钮 .stop 防误触。 -->
    <header class="message-head" :class="{ 'head-clickable': headClickable }" @click="onHeadClick">
      <strong>{{ message.role === 'user' ? '我的输入' : 'AI 助手' }}</strong>
      <div class="head-tools">
        <!-- 生成中前端计时（右上角）：思考+输出全程实时走秒，输出结束即停止并隐藏；最终耗时由下方统计条展示 -->
        <span v-if="message.role !== 'user' && message.pending" class="live-timer">
          <span class="live-dot" />{{ liveElapsedText }}
        </span>
        <!-- 复制：用户输入始终可复制（提交即定稿）；助手气泡仅本轮输出结束后显示 -->
        <el-button
          v-if="copyable && (message.role === 'user' ? message.content : (message.content || messageHasQuestions(message)))"
          link
          size="small"
          @click.stop="emit('copy', message.role === 'user' ? userCopyText(message) : assistantCopyText(message))"
        >
          复制
        </el-button>
        <!-- 用户输入：一键展开/收起气泡内全部区块（正文 + 各分块 + 合并来源）。 -->
        <el-button
          v-if="userHasBulkToggle"
          link
          size="small"
          @click.stop="setUserExpanded(!userAllExpanded)"
        >
          {{ userAllExpanded ? '全部收起' : '全部展开' }}
        </el-button>
        <!-- 助手输出完成后支持收起；用户输入的各内容区块分别管理展开状态。 -->
        <el-button
          v-if="message.role !== 'user' && !message.pending && (message.content || messageHasQuestions(message))"
          link
          size="small"
          @click.stop="message.outputOpen = !message.outputOpen"
        >
          {{ message.outputOpen ? '收起' : '展开' }}
        </el-button>
      </div>
    </header>

    <!-- 用户输入：超过 3 行默认收起，展开/收起由头部按钮控制 -->
    <div v-if="message.role === 'user'" class="user-body">
      <ConversationContentBlock
        :title="message.initial ? '任务说明' : '本轮输入'"
        :content="message.content"
        :model-value="!!message.contentOpen"
        :copyable="copyable"
        @update:model-value="message.contentOpen = $event"
        @copy="emit('copy', $event)"
      />
      <ConversationContentBlock
        v-for="section in message.contentSections || []"
        :key="section.key"
        :title="section.title"
        :content="section.content"
        :markdown="section.markdown"
        :model-value="!!section.open"
        :copyable="copyable"
        @update:model-value="section.open = $event"
        @copy="emit('copy', $event)"
      />
      <div v-if="message.answerDetails?.length" class="answer-details">
        <!-- 整行可点切换；默认收起（answerDetailsOpen 初值 false），复制不触发折叠。 -->
        <header class="answer-details__head" @click="message.answerDetailsOpen = !message.answerDetailsOpen">
          <span>本轮回答详情</span>
          <div class="head-tools">
            <el-button v-if="copyable" link size="small" @click.stop="emit('copy', answerDetailsCopyText(message))">复制</el-button>
            <el-button link size="small" @click.stop="message.answerDetailsOpen = !message.answerDetailsOpen">
              {{ message.answerDetailsOpen ? '收起' : '展开' }}
            </el-button>
          </div>
        </header>
        <div v-show="message.answerDetailsOpen" class="answer-details__body">
          <div v-for="item in message.answerDetails" :key="item.id || item.text" class="answer-detail-row">
            <strong>{{ item.text }}</strong>
            <span v-if="item.status === 'skipped'" class="answer-detail-status">已跳过</span>
            <span v-else-if="item.status === 'pending'" class="answer-detail-status">未处理</span>
            <template v-else>
              <span v-if="item.selected_options?.length">用户选择：{{ item.selected_options.join('、') }}</span>
              <span v-if="item.custom_answer">用户输入：{{ item.custom_answer }}</span>
              <span v-if="item.answer && !item.custom_answer && !item.selected_options?.length">{{ item.type === 'open' ? '用户输入' : '用户回答' }}：{{ item.answer }}</span>
            </template>
          </div>
        </div>
      </div>
      <div v-if="message.sourceSnapshots?.length" class="merge-sources">
        <!-- 组标题整行可点：点击=全部展开/收起，复制不触发折叠。 -->
        <div class="merge-sources__head" @click="setSourcesExpanded(!sourcesAllExpanded)">
          <div class="merge-sources__title">
            <span>{{ message.sourceTitle || '本次来源需求' }}</span>
            <span class="merge-sources__count">共 {{ message.sourceSnapshots.length }} 条</span>
          </div>
          <div class="head-tools">
            <!-- 复制（左）：一次性复制全部来源需求（编号·标题·正文） -->
            <el-button v-if="copyable" link size="small" @click.stop="emit('copy', sourcesCopyText())">复制</el-button>
            <el-button
              link
              size="small"
              @click.stop="setSourcesExpanded(!sourcesAllExpanded)"
            >
              {{ sourcesAllExpanded ? '全部收起' : '全部展开' }}
            </el-button>
          </div>
        </div>
        <div
          v-for="(source, index) in message.sourceSnapshots"
          :key="`${source.req_no}-${index}`"
          class="merge-source-card"
        >
          <ConversationContentBlock
            :title="source.req_no ? `${source.req_no} · ${source.title || '未命名需求'}` : source.title || '未命名需求'"
            :content="source.content || '需求正文为空'"
            :model-value="!!source.expanded"
            :copyable="copyable"
            @update:model-value="source.expanded = $event"
            @copy="emit('copy', $event)"
          />
          <div class="merge-source-card__meta">
            <span class="merge-source-card__dot" />
            <span>来源需求</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 助手 -->
    <template v-else>
      <!-- 思考过程：思考中默认展开、结束后默认收起。
           思考一结束（reasoningDone，即使正文仍在流式输出）即可展开/收起并复制思考内容，无需等整轮完成。 -->
      <div v-if="message.reasoning" class="reasoning-box">
        <div class="reasoning-head">
          <span>思考过程</span>
          <div class="head-tools">
            <el-button
              v-if="copyable && (message.reasoningDone || !message.pending)"
              link
              size="small"
              @click="emit('copy', message.reasoning)"
            >
              复制
            </el-button>
            <el-button link size="small" @click="message.reasoningOpen = !message.reasoningOpen">
              {{ message.reasoningOpen ? '收起' : '展开' }}
            </el-button>
          </div>
        </div>
        <pre v-show="message.reasoningOpen">{{ message.reasoning }}</pre>
      </div>

      <!-- 生成中 -->
      <div v-if="message.pending" class="thinking-status">
        <span class="thinking-dot" />{{ supportsReasoning ? 'AI 正在思考并整理回复…' : 'AI 正在整理回复…' }}
      </div>

      <!-- 输出正文：默认展开，支持收起 -->
      <template v-else>
        <div v-show="message.outputOpen" class="assistant-output">
          <div v-if="message.error" class="message-content error-text">{{ message.content }}</div>
          <div v-else-if="message.content && isMarkdown(message.content)" class="message-content markdown-content markdown-body" v-html="renderMarkdown(message.content)" />
          <p v-else-if="message.content" class="message-content">{{ message.content }}</p>

          <!-- 模型/服务报错：以 AI 回复的形式留在对话流，允许用户确认额度影响后原轮重试。 -->
          <div v-if="message.error" class="error-actions">
            <p v-if="message.errorHint" class="error-hint">{{ message.errorHint }}</p>
            <div class="error-actions-row">
              <!-- 合并后的单一入口：点击打开弹窗，弹窗内会重新获取最新可用模型并刷新各模型实时额度，
                   由用户手动选择后重试。仅对携带上下文快照（retryAction）的报错气泡展示，
                   否则重试会丢失上下文。 -->
              <el-button
                v-if="hasRetryAction"
                class="error-action-button"
                type="primary"
                size="small"
                :loading="retryModelLoading"
                :disabled="!isLatestMessage || retryModelLoading"
                :title="!isLatestMessage ? '仅可重试最新一次失败' : '打开后会重新获取可用模型并刷新额度，选择模型后重试'"
                @click="openRetryDialog"
              >重试</el-button>
              <el-button class="error-action-button" type="default" size="small" @click="openModelConfig">去配置模型</el-button>
            </div>
            <AiRetryModelDialog
              v-model="retryDialogVisible"
              :model-info="retryModelInfo"
              :model-candidates="retryCandidates"
              :loading="retryModelLoading"
              @open="emit('retry-open', message.id)"
              @refresh="emit('retry-open', message.id)"
              @confirm="confirmRetry"
            />
          </div>

          <RefinementQuestionGroups
            :groups="message.groups || []"
            :interactive="message.id === activeQuestionId"
            :draft="answerDraft"
            :answer-snapshot="message.answerSnapshot || {}"
            :can-submit="canSubmit"
            :can-end="canEnd"
            :end-loading="endLoading"
            :end-label="endLabel"
            :merge-mode="mergeMode"
            @answer-change="(id, patch) => emit('answer-change', id, patch)"
            @submit="emit('submit')"
            @end="emit('end')"
          />

          <!-- 无待答问题（stepper 不渲染）时的兜底：在最新一条追问气泡内给出结束入口，避免找不到收尾按钮 -->
          <div v-if="message.id === endActionId && !messageHasQuestions(message) && !message.action" class="message-action">
            <div v-if="message.supplementEnabled" class="supplement-box">
              <div class="supplement-heading">
                <span>还有补充内容吗？</span>
                <span>补充后 AI 会继续追问</span>
              </div>
              <el-input
                v-model="supplementText"
                type="textarea"
                :rows="2"
                resize="none"
                maxlength="1000"
                show-word-limit
                placeholder="可补充业务规则、边界条件或遗漏场景"
                :disabled="retrySelectionRequired"
              />
              <div class="supplement-actions">
                <el-button type="primary" plain :disabled="retrySelectionRequired || !supplementText.trim()" @click="submitSupplement">继续追问</el-button>
                <el-button
                  class="end-conversation-btn"
                  type="success"
                  plain
                  :icon="CircleCheck"
                  :loading="endLoading"
                  :disabled="retrySelectionRequired || !canEnd"
                  @click="emit('end')"
                >
                  {{ endLabel }}
                </el-button>
              </div>
            </div>
            <el-button
              v-else
              class="end-conversation-btn"
              type="success"
              plain
              :icon="CircleCheck"
              :loading="endLoading"
              :disabled="retrySelectionRequired || !canEnd"
              @click="emit('end')"
            >
              {{ endLabel }}
            </el-button>
          </div>

          <p v-else-if="!message.content && !messageHasQuestions(message) && !message.action" class="all-clear-hint">
            AI 未发现仍需确认的问题，可结束对话并补全需求。
          </p>

          <!-- 整理成文结果：挂「预览并保存」按钮；仅最新一条可点，早前的置灰 -->
          <div v-if="message.action === 'preview-save'" class="message-action">
            <el-button
              type="primary"
              :icon="View"
              :disabled="message.id !== activeActionId"
              @click="emit('preview', message.id)"
            >
              预览并保存
            </el-button>
            <el-button
              :icon="View"
              :disabled="message.id !== activeActionId"
              @click="emit('compare')"
            >
              预览并对比
            </el-button>
            <span v-if="message.id !== activeActionId" class="action-outdated">已生成更新版本，请使用最新整理结果</span>
          </div>
          <div v-else-if="message.action === 'comparison-preview'" class="message-action">
            <el-button type="primary" :icon="View" @click="emit('comparison-preview', message.comparisonResult)">查看对比结果</el-button>
          </div>
          <div v-else-if="message.action === 'case-preview'" class="message-action">
            <el-button
              type="primary"
              :icon="View"
              :disabled="message.id !== activeActionId"
              @click="emit('case-preview', message.generatedResult)"
            >
              查看并保存测试用例
            </el-button>
          </div>
        </div>
      </template>

      <!-- 本轮统计：模型成功时展示真实 token；报错或停止时仅展示可确认的轮次与等待耗时。 -->
      <AiUsageStatsBar
        v-if="!message.pending && (message.round || message.round === 0)"
        :round="message.round"
        :usage="message.usage || null"
        :elapsed-ms="message.clientElapsedMs ?? null"
        :model="message.modelMeta || null"
      />
    </template>
  </article>
</template>

<script setup>
import { ref, computed, watch, onUnmounted } from 'vue'
import { renderMarkdown } from '@/utils/markdown'
import { View, CircleCheck } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import RefinementQuestionGroups from './RefinementQuestionGroups.vue'
import AiUsageStatsBar from '@/components/AiUsageStatsBar.vue'
import ConversationContentBlock from './ConversationContentBlock.vue'
import AiRetryModelDialog from './AiRetryModelDialog.vue'

const props = defineProps({
  message: { type: Object, required: true },
  copyable: Boolean,
  supportsReasoning: Boolean,
  // 当前可点的「预览并保存」按钮所属消息 id：只有最新一条整理结果可点
  activeActionId: { type: String, default: '' },
  // 最新一条追问气泡 id：当该气泡没有待答问题时，在其内兜底展示「结束对话并补全需求」按钮
  endActionId: { type: String, default: '' },
  endLabel: { type: String, default: '结束对话并补全需求' },
  endLoading: Boolean,
  mergeMode: Boolean,
  // 当前可交互作答的追问气泡 id（仅最新一条待答气泡），及其逐题作答草稿
  activeQuestionId: { type: String, default: '' },
  answerDraft: { type: Object, default: () => ({}) },
  // 是否可提交本轮（透传给单题分步的「提交回答」按钮）
  canSubmit: Boolean,
  // 是否可「结束对话并补全需求」（透传给单题分步动作行与兜底按钮）
  canEnd: Boolean,
  // 模型调用失败后，必须先选择模型重试，禁止继续提交或补充。
  retrySelectionRequired: Boolean,
  retryModelLoading: Boolean,
  // 是否为对话流中最新一条消息：仅最新一条失败气泡可重试，避免点历史失败气泡回退上下文。
  isLatestMessage: Boolean,
})
const emit = defineEmits(['copy', 'preview', 'case-preview', 'comparison-preview', 'compare', 'end', 'answer-change', 'submit', 'supplement', 'retry', 'retry-open'])

const supplementText = ref('')
const retryDialogVisible = ref(false)
const router = useRouter()
const submitSupplement = () => {
  const value = supplementText.value.trim()
  if (!value) return
  supplementText.value = ''
  emit('supplement', value)
}

const retryCandidates = computed(() => Array.isArray(props.message.retryAction?.retryCandidates)
  ? props.message.retryAction.retryCandidates
  : [])
// 仅携带上下文快照（retryAction）的报错气泡才允许重试；无快照的报错路径不展示入口，避免重试丢上下文。
const hasRetryAction = computed(() => !!props.message.retryAction)
const retryModelInfo = computed(() => props.message.retryAction?.currentModel || {
  id: props.message.retryAction?.modelId,
  name: props.message.retryAction?.currentModelName || props.message.retryAction?.modelName,
  scope: props.message.retryAction?.currentModelScope || 'platform',
})
// 合并后的唯一入口：不再要求"已有候选模型"才可点——弹窗打开后会实时向后端获取最新可用模型并刷新额度。
const openRetryDialog = () => {
  if (props.retryModelLoading || !props.isLatestMessage) return
  retryDialogVisible.value = true
}
const openModelConfig = () => {
  const target = router.resolve({ name: 'ModelAdminModelsMine' })
  window.open(target.href, '_blank', 'noopener,noreferrer')
}
const confirmRetry = modelId => {
  retryDialogVisible.value = false
  emit('retry', { messageId: props.message.id, modelId, confirmed: true })
}
// 前端实时计时：助手气泡进入生成中（pending）即开始走秒，覆盖思考 + 输出全程；
// 输出结束（pending 置 false）立即停止并隐藏。最终精确耗时由后端返回、下方统计条展示，
// 此处仅为生成过程中的即时反馈，避免长时间空等时用户以为卡死。
const liveElapsedMs = ref(0)
let liveTimer = null
let liveStart = 0
const stopLiveTimer = () => {
  if (liveTimer) {
    clearInterval(liveTimer)
    liveTimer = null
  }
}
const startLiveTimer = () => {
  stopLiveTimer()
  liveStart = Date.now()
  liveElapsedMs.value = 0
  liveTimer = setInterval(() => { liveElapsedMs.value = Date.now() - liveStart }, 100)
}
watch(
  () => props.message.role === 'assistant' && props.message.pending,
  isGenerating => { isGenerating ? startLiveTimer() : stopLiveTimer() },
  { immediate: true },
)
onUnmounted(stopLiveTimer)
// 计时文案：始终保留 1 位小数的秒，走秒时视觉稳定不跳动
const liveElapsedText = computed(() => `${(liveElapsedMs.value / 1000).toFixed(1)}s`)

const messageHasQuestions = message => (message.groups || []).some(group => (group.items || []).length)
const isMarkdown = content => /(^|\n)\s{0,3}(#{1,6}\s+|[-*+]\s+|\d+\.\s+|>\s+|```)|\[[^\]]+\]\([^\s)]+\)|(`[^`]+`|\*\*[^*]+\*\*|__[^_]+__)/m.test(content || '')
// renderMarkdown 已内置 DOMPurify 消毒，AI 输出直接 v-html 渲染无 XSS 风险。

// 「本轮回答详情」单独复制：逐题回显用户选择/输入/跳过，与整块复制口径一致。
const answerDetailsCopyText = message => {
  const answers = (message.answerDetails || []).map(item => {
    if (item.status === 'skipped') return `- ${item.text}：已跳过`
    if (item.status === 'pending') return `- ${item.text}：未处理`
    const selected = item.selected_options?.length ? `用户选择：${item.selected_options.join('、')}` : ''
    const custom = item.custom_answer ? `用户输入：${item.custom_answer}` : ''
    const finalAnswer = item.answer && !selected && !custom
      ? `${item.type === 'open' ? '用户输入' : '用户回答'}：${item.answer}`
      : ''
    return `- ${item.text}：${[selected, custom, finalAnswer].filter(Boolean).join('；') || '已回答'}`
  })
  return `## 本轮回答详情\n\n${answers.join('\n')}`
}

const userCopyText = message => {
  const parts = []
  if (message.content) parts.push(`## ${message.initial ? '任务说明' : '本轮输入'}\n\n${message.content}`)
  if (message.answerDetails?.length) parts.push(answerDetailsCopyText(message))
  for (const section of message.contentSections || []) {
    if (section.content) parts.push(`## ${section.title}\n\n${section.content}`)
  }
  const sources = message.sourceSnapshots || []
  for (const source of sources) {
    const title = [source.req_no, source.title || '未命名需求'].filter(Boolean).join(' · ')
    parts.push(`## ${title}\n\n${source.content || ''}`)
  }
  return parts.join('\n\n---\n\n')
}

const setSourcesExpanded = expanded => {
  for (const source of props.message.sourceSnapshots || []) source.expanded = expanded
}

// 「本次合并来源」整块复制 = 各原始需求（编号·标题·正文）依次拼接，与 userCopyText 中来源格式保持一致。
const sourcesCopyText = () => {
  const parts = []
  for (const source of props.message.sourceSnapshots || []) {
    const title = [source.req_no, source.title || '未命名需求'].filter(Boolean).join(' · ')
    parts.push(`## ${title}\n\n${source.content || ''}`)
  }
  return parts.join('\n\n---\n\n')
}

// 「本次合并来源」是否全部展开，供头部单个「全部展开/全部收起」切换按钮使用。
const sourcesAllExpanded = computed(() => {
  const sources = props.message.sourceSnapshots || []
  return sources.length > 0 && sources.every(source => !!source.expanded)
})

// 「我的输入」气泡内所有可折叠区块（正文 + 各分块 + 合并来源）的统一展开状态。
const userExpandStates = computed(() => {
  const m = props.message
  const states = []
  if (m.content) states.push(!!m.contentOpen)
  for (const section of m.contentSections || []) states.push(!!section.open)
  if (m.answerDetails?.length) states.push(!!m.answerDetailsOpen)
  for (const source of m.sourceSnapshots || []) states.push(!!source.expanded)
  return states
})
// 仅当存在两个及以上可折叠区块时，「全部展开/收起」才有意义。
const userHasBulkToggle = computed(() => props.message.role === 'user' && userExpandStates.value.length > 1)
const userAllExpanded = computed(() => userExpandStates.value.length > 0 && userExpandStates.value.every(Boolean))
const setUserExpanded = expanded => {
  const m = props.message
  if (m.content) m.contentOpen = expanded
  for (const section of m.contentSections || []) section.open = expanded
  if (m.answerDetails?.length) m.answerDetailsOpen = expanded
  for (const source of m.sourceSnapshots || []) source.expanded = expanded
}

// 助手气泡整行标题可点收起/展开正文（仅本轮输出结束、且有正文或问题时）。
const assistantHeadToggleable = computed(() =>
  props.message.role !== 'user'
  && !props.message.pending
  && (props.message.content || messageHasQuestions(props.message)),
)
// 顶部标题整行是否可点：用户气泡有多区块 → 全部展开/收起；助手气泡 → 收起/展开正文。
const headClickable = computed(() =>
  props.message.role === 'user' ? userHasBulkToggle.value : assistantHeadToggleable.value,
)
const onHeadClick = () => {
  if (props.message.role === 'user') {
    if (userHasBulkToggle.value) setUserExpanded(!userAllExpanded.value)
    return
  }
  if (assistantHeadToggleable.value) props.message.outputOpen = !props.message.outputOpen
}

// 助手输出复制内容 = 正文导语 + 结构化问题（保持人类可读；问题项为结构化对象，取其 text 与候选项）
const assistantCopyText = message => {
  const parts = []
  if (message.content) parts.push(message.content)
  let number = 1
  for (const group of message.groups || []) {
    if (!(group.items || []).length) continue
    parts.push(`【${group.label}】`)
    for (const item of group.items) {
      const options = (item.options || []).length ? `（候选：${item.options.join(' / ')}）` : ''
      parts.push(`${number}. ${item.text}${options}`)
      number += 1
    }
  }
  return parts.join('\n')
}

</script>

<style scoped>
.message-card {
  margin: 0 0 14px;
  padding: 14px 16px;
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  background: var(--el-bg-color);
}
.message-card.user {
  margin-left: 18%;
  background: var(--el-color-primary-light-9);
  border-color: var(--el-color-primary-light-7);
}
/* 与上方「任务说明 / AI 身份」分块之间隔一条分割线（与上方分块同款实线），凸显「本次合并来源」是独立整块。 */
.merge-sources { margin-top: 12px; padding: 14px 10px 2px; border-top: 1px solid var(--el-color-primary-light-7); }
.merge-sources__head { display: flex; align-items: center; justify-content: space-between; gap: 12px; min-height: 30px; cursor: pointer; user-select: none; }
.merge-sources__head:hover .merge-sources__title { color: var(--el-color-primary); }
.merge-sources__title { display: flex; align-items: center; gap: 6px; color: var(--el-text-color-regular); font-size: 13px; font-weight: 600; }
.merge-sources__count { padding: 1px 6px; border-radius: 10px; background: var(--el-color-primary-light-8); color: var(--el-color-primary); font-size: 12px; font-weight: 400; }
.merge-source-card {
  margin-top: 8px;
  padding: 0 10px 8px;
  border: 1px solid var(--el-color-primary-light-6);
  border-radius: 6px;
  background: var(--el-bg-color);
}
.merge-source-card :deep(.conversation-content-block) { margin-top: 0; border-top: 0; }
.merge-source-card :deep(.content-block-head) { min-width: 0; min-height: 38px; }
.merge-source-card :deep(.content-block-head > span) {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.merge-source-card :deep(.content-block-actions) { flex-shrink: 0; }
.merge-source-card :deep(.content-block-body) {
  margin-bottom: 0;
  border: 1px solid var(--el-border-color-lighter);
  background: var(--el-fill-color-lighter);
}
.merge-source-card__meta {
  display: flex;
  align-items: center;
  gap: 5px;
  margin-top: 7px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
.merge-source-card__dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--el-color-primary-light-4);
}
.message-card.error {
  border-color: var(--el-color-danger-light-5);
  background: var(--el-color-danger-light-9);
}
.message-card.error .message-head strong,
.message-card.error .message-content {
  color: var(--el-color-danger);
}
.answer-details {
  margin-top: 12px;
  padding: 10px 12px;
  border: 1px solid var(--el-color-primary-light-7);
  border-radius: 6px;
  background: var(--el-bg-color);
}
.answer-details__head { display: flex; align-items: center; justify-content: space-between; gap: 12px; min-height: 30px; color: var(--el-text-color-primary); font-size: 13px; font-weight: 600; cursor: pointer; user-select: none; }
.answer-details__head:hover { color: var(--el-color-primary); }
.answer-details__head > span { flex: 1; min-width: 0; }
.answer-details__body { margin-top: 7px; }
.answer-detail-row { display: flex; flex-wrap: wrap; gap: 5px 10px; padding: 5px 0; color: var(--el-text-color-regular); font-size: 12px; line-height: 1.6; }
.answer-detail-row strong { flex: 1 1 100%; color: var(--el-text-color-primary); font-weight: 500; }
.answer-detail-status { color: var(--el-color-warning); }
.message-head,
.reasoning-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
/* 顶部标题整行可点：用户气泡=全部展开/收起，助手气泡=收起/展开正文 */
.message-head.head-clickable {
  cursor: pointer;
  user-select: none;
}
.message-head.head-clickable:hover strong {
  color: var(--el-color-primary);
}
.message-head strong {
  color: var(--el-text-color-primary);
  font-size: 14px;
}
.head-tools {
  display: flex;
  align-items: center;
  gap: 4px;
}
/* 生成中前端计时：右上角轻量走秒，与状态点同色，输出结束即隐藏 */
.live-timer {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 1px 8px;
  border-radius: 10px;
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}
.live-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
  animation: pulse 1s ease-in-out infinite;
}
.head-tools :deep(.el-button) {
  height: auto;
  padding: 0 2px;
}
.message-content {
  margin: 8px 0 0;
  color: var(--el-text-color-primary);
  white-space: pre-wrap;
  line-height: 1.8;
}
/* 正文排版（标题/表格/代码/hr…）统一在 src/styles/markdown.css 的 .markdown-body，此处不再重复。
   这里只需覆盖 .message-content 的 pre-wrap：Markdown 已转成块级标签，
   再保留标签间的换行会在段落之间多出成片空行。 */
.markdown-content {
  white-space: normal;
}
/* 气泡宽度有限，宽表格/长代码横向滚动，不撑破卡片 */
.markdown-content :deep(table),
.markdown-content :deep(pre) {
  max-width: 100%;
}
/* 报错正文：保留模型返回的原始换行，长报文可横向滚动而不撑破气泡 */
.error-text {
  overflow-x: auto;
  word-break: break-word;
}
.error-hint {
  margin: 0;
  padding: 10px 12px;
  border-radius: 6px;
  background: var(--el-fill-color-light);
  color: var(--el-text-color-regular);
  font-size: 13px;
  line-height: 1.7;
}
.error-actions {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 8px;
  margin-top: 12px;
}
.error-actions .error-hint {
  width: 100%;
  box-sizing: border-box;
}
.error-actions-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.error-action-button {
  min-width: 96px;
  height: 32px;
  padding: 0 14px;
  border-radius: 6px;
  font-weight: 600;
}
.error-actions :deep(.retry-model-selector) { width: 100%; }
.error-actions :deep(.el-button) {
  flex-shrink: 0;
}
.retry-model-selector {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  width: 100%;
}
.retry-model-select { min-width: 260px; max-width: 420px; }
.retry-model-option { display: flex; align-items: center; gap: 8px; min-width: 0; }
.retry-model-option span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.retry-model-option small { overflow: hidden; color: var(--el-text-color-secondary); text-overflow: ellipsis; white-space: nowrap; }
.retry-empty-hint { color: var(--el-text-color-secondary); font-size: 13px; }
.retry-required-hint { margin: 8px 0 0; color: var(--el-color-warning); font-size: 13px; }
.all-clear-hint {
  margin: 12px 0 0;
  padding: 10px 12px;
  border-radius: 6px;
  background: var(--el-color-success-light-9);
  color: var(--el-color-success);
  font-size: 13px;
}
.message-action {
  display: flex;
  align-items: flex-end;
  gap: 12px;
  margin-top: 16px;
}
.supplement-box {
  flex: 1;
  min-width: 0;
  padding: 10px 12px 12px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  background: var(--el-fill-color-lighter);
}
.supplement-heading {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-bottom: 8px;
  color: var(--el-text-color-regular);
  font-size: 13px;
  font-weight: 600;
}
.supplement-heading span:last-child {
  color: var(--el-text-color-secondary);
  font-size: 12px;
  font-weight: 400;
}
.supplement-box {
  padding: 10px;
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  background: var(--el-bg-color);
}
.supplement-box :deep(.el-textarea__inner) {
  min-height: 56px !important;
  background: var(--el-bg-color);
}
.supplement-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 8px; }
.supplement-actions :deep(.el-button) { min-width: 88px; height: 32px; margin: 0; }
.end-conversation-btn {
  flex-shrink: 0;
  height: 34px;
  margin: 0;
}
.action-outdated {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

/* 思考过程 */
.reasoning-box {
  margin-top: 10px;
  padding: 10px 12px;
  border-radius: 6px;
  background: var(--el-fill-color-light);
}
.reasoning-head {
  color: var(--el-text-color-regular);
  font-size: 13px;
}
.reasoning-box pre {
  margin: 8px 0 0;
  color: var(--el-text-color-regular);
  font: 12px/1.7 ui-monospace, SFMono-Regular, Menlo, monospace;
  white-space: pre-wrap;
}
.thinking-status {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 10px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
.thinking-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--el-color-primary);
  animation: pulse 1s ease-in-out infinite;
}

@keyframes pulse {
  50% {
    opacity: 0.3;
    transform: scale(0.75);
  }
}
</style>
