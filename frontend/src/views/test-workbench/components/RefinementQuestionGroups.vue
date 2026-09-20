<template>
  <!-- 交互作答：Claude Code 式单题分步（一次一题，可上一题/下一题/跳过），仅最新一轮追问气泡 -->
  <section v-if="interactive && flatQuestions.length" class="question-stepper">
    <!-- 进度条：题号 + 所属分组 + 必答标记 -->
    <div class="stepper-head">
      <span class="step-count">第 {{ index + 1 }} / {{ flatQuestions.length }} 题</span>
      <el-tag class="step-group" :type="groupTagType(current.groupKey)" size="small" effect="light" round>{{ current.groupLabel }}</el-tag>
      <el-tag v-if="current.blocking" size="small" type="danger" effect="plain" round>必答</el-tag>
    </div>

    <!-- 进度点：一眼看清各题状态（已答/已跳过/未答/当前），可点击跳转 -->
    <div class="step-dots">
      <button
        v-for="(question, i) in flatQuestions"
        :key="question.id"
        type="button"
        class="dot"
        :class="[statusOf(question), { active: i === index }]"
        :title="`第 ${i + 1} 题`"
        @click="index = i"
      />
    </div>

    <!-- 当前问题正文 -->
    <p class="question-text">{{ current.text }}</p>

    <!-- 作答区（跳过时置灰禁用） -->
    <div class="question-controls" :class="{ disabled: draftOf(current.id).action === 'skip' }">
      <!-- 选择题：候选项竖向排列，推荐项高亮，单选 / 多选 -->
      <template v-if="current.type === 'choice' && (current.options || []).length">
        <!-- 一旦填写了自定义答案，预设选项整体置灰：本题最终只取用户输入的意见 -->
        <el-checkbox-group
          v-if="current.multi"
          :model-value="isCustomFilled(current.id) ? [] : draftOf(current.id).selected"
          :disabled="isCustomFilled(current.id)"
          class="option-group"
          @update:model-value="onSelect(current, $event)"
        >
          <el-checkbox
            v-for="(option, oi) in current.options"
            :key="option"
            :value="option"
            :label="option"
            border
            class="option-item"
            :class="{ recommended: option === current.recommended }"
            :style="optionStyle(oi)"
          >
            <span class="opt-text">{{ option }}</span>
            <span v-if="option === current.recommended" class="rec-badge">推荐</span>
            <span v-if="isLong(option)" class="detail-link" @click.stop.prevent="openDetail(option)">查看详情</span>
          </el-checkbox>
        </el-checkbox-group>
        <el-radio-group
          v-else
          :model-value="isCustomFilled(current.id) ? '' : (draftOf(current.id).selected[0] || '')"
          :disabled="isCustomFilled(current.id)"
          class="option-group"
          @update:model-value="onSelect(current, [$event])"
        >
          <el-radio
            v-for="(option, oi) in current.options"
            :key="option"
            :value="option"
            :label="option"
            border
            class="option-item"
            :class="{ recommended: option === current.recommended }"
            :style="optionStyle(oi)"
          >
            <span class="opt-text">{{ option }}</span>
            <span v-if="option === current.recommended" class="rec-badge">推荐</span>
            <span v-if="isLong(option)" class="detail-link" @click.stop.prevent="openDetail(option)">查看详情</span>
          </el-radio>
        </el-radio-group>

        <!-- 每道选择题都支持自定义输入：AI 给的选项未必有用户想要的答案。
             填写后上方选项置灰，本题只采纳此处输入。 -->
        <el-input
          :model-value="draftOf(current.id).custom"
          size="small"
          class="custom-input choice-custom-input"
          placeholder="其他（自定义答案，填写后将只采纳此处内容）"
          clearable
          @update:model-value="onCustom(current.id, $event)"
        />
        <p v-if="isCustomFilled(current.id)" class="custom-hint">已填写自定义答案，上方选项不再计入本题。</p>
      </template>

      <!-- 开放题：直接文本作答 -->
      <el-input
        v-else
        :model-value="draftOf(current.id).custom"
        type="textarea"
        :rows="3"
        resize="none"
        class="custom-input"
        placeholder="请描述你的答案"
        @update:model-value="onCustom(current.id, $event)"
      />
    </div>

    <!-- 导航：上一题 / 跳过此题（并进入下一题） / 下一题（最后一题换成「提交回答」） / 结束对话并补全需求 -->
    <div class="stepper-actions">
      <el-button size="small" :icon="ArrowLeft" :disabled="index === 0" @click="prev">上一题</el-button>
      <el-button size="small" @click="skipCurrent">跳过此题</el-button>
      <el-button
        v-if="!isLastQuestion"
        size="small"
        type="primary"
        @click="next"
      >
        下一题<el-icon class="el-icon--right"><ArrowRight /></el-icon>
      </el-button>
      <el-button
        v-else
        size="small"
        type="primary"
        :icon="Promotion"
        :disabled="!canSubmit"
        @click="emit('submit')"
      >
        提交回答
      </el-button>
      <el-button
        size="small"
        type="success"
        plain
        :icon="CircleCheck"
        :loading="endLoading"
        :disabled="!canEnd"
        class="end-btn"
        @click="emit('end')"
      >
        {{ endLabel }}
      </el-button>
    </div>
    <p class="stepper-hint">
      逐题作答或跳过；答完点「提交回答」提交本轮（<b>整组一次提交只消耗 1 次额度，与题目数量无关</b>），未作答的题会留到下一轮继续追问；跳过的题不再重复询问，也不会被当作确定规则。
    </p>
  </section>

  <!-- 只读展示（历史气泡）：按分组列出问题与候选项供回溯 -->
  <template v-else>
    <section
      v-for="group in visibleGroups"
      :key="group.key"
      class="question-group"
      :class="group.key"
    >
      <h4>{{ group.label }}</h4>
      <div class="question-list">
        <div v-for="question in group.items" :key="question.id" class="question-item">
          <p class="question-text readonly">
            {{ question.text }}
            <el-tag v-if="question.blocking" size="small" type="danger" effect="plain" round>必答</el-tag>
          </p>
          <div v-if="readonlyAnswer(question.id) && readonlyAnswer(question.id)?.action !== 'skip'" class="readonly-answer">
            <span class="readonly-answer-label">{{ readonlyAnswerLabel(question.id, question.type) }}：</span>
            <span>{{ readonlyAnswerText(question.id) }}</span>
          </div>
          <p v-if="readonlyAnswer(question.id)?.action === 'skip'" class="readonly-answer skipped">已跳过</p>
        </div>
      </div>
    </section>
  </template>

  <!-- 长选项「查看详情」共用小弹窗：避免用超长 popover 撑破卡片 -->
  <el-dialog
    v-model="detailVisible"
    title="选项详情"
    width="640px"
    append-to-body
    :close-on-click-modal="true"
    class="option-detail-dialog"
  >
    <div class="opt-detail">{{ detailContent }}</div>
  </el-dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { ArrowLeft, ArrowRight, CircleCheck, Promotion } from '@element-plus/icons-vue'
import { ElMessageBox } from 'element-plus'

const props = defineProps({
  // 结构化问题分组：[{ key, label, items: [structuredQuestion] }]
  groups: { type: Array, default: () => [] },
  // 是否可交互作答（仅最新一轮追问气泡为 true，历史气泡只读）
  interactive: { type: Boolean, default: false },
  // 逐题作答草稿：{ [id]: { action, selected, custom } }
  draft: { type: Object, default: () => ({}) },
  // 已结束的历史问题依靠当轮答案快照回显，避免当前草稿清空后丢失用户选择。
  answerSnapshot: { type: Object, default: () => ({}) },
  // 是否可提交本轮（与底部提交按钮同一条件：至少作答一题或有补充说明）
  canSubmit: { type: Boolean, default: false },
  // 是否可「结束对话并补全需求」（首轮须先处理关键问题并提交一次；此后可点）
  canEnd: { type: Boolean, default: false },
  // 「结束对话并补全需求」是否处于整理中（loading）
  endLoading: { type: Boolean, default: false },
  endLabel: { type: String, default: '结束对话并补全需求' },
  mergeMode: Boolean,
})
const emit = defineEmits(['answer-change', 'submit', 'end'])

// 较长候选项保留「查看详情」入口；选项内仍完整展示，避免按固定字数提前截断。
const LONG_OPTION_LEN = 80

const visibleGroups = computed(() => (props.groups || []).filter(group => (group.items || []).length))
// 交互态把分组拍平成有序单题列表（保留分组标签），供分步作答逐题展示。
const flatQuestions = computed(() =>
  visibleGroups.value.flatMap(group =>
    group.items.map(question => ({ ...question, groupLabel: group.label, groupKey: group.key })),
  ),
)

const draftOf = id => props.draft[id] || { action: 'answer', selected: [], custom: '' }
const readonlyAnswer = id => props.answerSnapshot[id] || null
const readonlyAnswerText = id => {
  const answer = readonlyAnswer(id)
  if (!answer) return '未回答'
  if (String(answer.custom || '').trim()) return answer.custom
  if (Array.isArray(answer.selected) && answer.selected.length) return answer.selected.join('、')
  if (String(answer.answer || '').trim()) return answer.answer
  return '未回答'
}
const readonlyAnswerLabel = (id, questionType = '') => {
  const answer = readonlyAnswer(id)
  if (String(answer?.custom || '').trim() || questionType === 'open') return '用户输入'
  if (Array.isArray(answer?.selected) && answer.selected.length) return '用户选择'
  return '用户回答'
}
const statusOf = question => {
  const draft = draftOf(question.id)
  if (draft.action === 'skip') return 'skip'
  const answered = (Array.isArray(draft.selected) && draft.selected.filter(Boolean).length) || String(draft.custom || '').trim()
  return answered ? 'answered' : 'pending'
}

const groupTagType = groupKey => ({
  conflicts: 'warning',
  missing_scenarios: 'info',
  suggestions: 'success',
}[groupKey] || 'primary')

const isLong = option => String(option || '').length > LONG_OPTION_LEN

// 长选项「查看详情」共用小弹窗
const detailVisible = ref(false)
const detailContent = ref('')
const openDetail = option => {
  detailContent.value = String(option || '')
  detailVisible.value = true
}

// 本题是否已填写自定义答案：填写后预设选项整体置灰，最终只采纳自定义输入。
const isCustomFilled = id => String(draftOf(id).custom || '').trim().length > 0

// 候选项浅淡背景色：按位置轮换一组低饱和柔色，区分不同选项、不喧宾夺主。
const OPTION_TINTS = [
  'rgba(64, 158, 255, 0.07)',   // 蓝
  'rgba(103, 194, 58, 0.08)',   // 绿
  'rgba(230, 162, 60, 0.08)',   // 橙
  'rgba(155, 109, 255, 0.08)',  // 紫
]
const optionStyle = oi => ({ background: OPTION_TINTS[oi % OPTION_TINTS.length] })

// 当前题指针；问题集变化（新一轮追问到达）时归零。
const index = ref(0)
const current = computed(() => flatQuestions.value[index.value] || { id: '', options: [] })
const isLastQuestion = computed(() => index.value >= flatQuestions.value.length - 1)
watch(
  () => flatQuestions.value.map(question => question.id).join('|'),
  () => { index.value = 0 },
)

const prev = () => { if (index.value > 0) index.value -= 1 }
const next = () => { if (index.value < flatQuestions.value.length - 1) index.value += 1 }
// 跳过当前题：标记 skip 并自动进入下一题；后续只基于已确认信息生成，不替用户补定规则。
// 不提供「取消跳过」——若误跳，回到该题选任意选项 / 填写自定义即自动恢复为作答（见 onSelect / onCustom）。
const skipCurrent = async () => {
  if (props.mergeMode && current.value.groupKey === 'conflicts') {
    try {
      await ElMessageBox.confirm(
        '跳过后，AI 不会替你选择规则；整理合并需求时会保留双方规则，并说明各自适用条件。是否继续跳过？',
        '确认跳过冲突',
        { confirmButtonText: '继续跳过', cancelButtonText: '返回作答', type: 'warning' },
      )
    } catch {
      return
    }
  }
  emit('answer-change', current.value.id, { action: 'skip' })
  next()
}

// 选择项变化：切回作答动作（若之前跳过），写入 selected。
const onSelect = (question, value) => {
  const selected = Array.isArray(value) ? value.filter(Boolean) : [value].filter(Boolean)
  emit('answer-change', question.id, { action: 'answer', selected })
}
const onCustom = (id, value) => {
  emit('answer-change', id, { action: 'answer', custom: value })
}
</script>

<style scoped>
/* ===== 交互态：单题分步 ===== */
.question-stepper {
  margin-top: 12px;
  padding: 12px 14px;
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  background: var(--el-bg-color);
}
.stepper-head {
  display: flex;
  align-items: center;
  gap: 8px;
}
.step-count {
  color: var(--el-text-color-primary);
  font-size: 13px;
  font-weight: 600;
}
.step-group {
  white-space: nowrap;
}

.step-dots {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin: 10px 0 4px;
}
.dot {
  width: 10px;
  height: 10px;
  padding: 0;
  border: 1px solid var(--el-border-color);
  border-radius: 50%;
  background: var(--el-fill-color-blank);
  cursor: pointer;
  transition: transform 0.1s ease;
}
.dot.answered { background: var(--el-color-success); border-color: var(--el-color-success); }
.dot.skip { background: var(--el-text-color-disabled); border-color: var(--el-text-color-disabled); }
.dot.active { transform: scale(1.4); box-shadow: 0 0 0 2px var(--el-color-primary-light-7); border-color: var(--el-color-primary); }

.question-text {
  margin: 8px 0 0;
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--el-text-color-primary);
  font-size: 14px;
  line-height: 1.7;
}
.question-controls { margin-top: 10px; }
.question-controls.disabled { pointer-events: none; opacity: 0.5; }

/* 候选项：竖向排列，整行可点 */
.option-group {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 8px;
}
.option-item {
  width: 100%;
  min-height: 40px;
  height: auto;
  margin: 0 !important;
  padding: 8px 12px;
  white-space: normal;
}
.option-item :deep(.el-radio__label),
.option-item :deep(.el-checkbox__label) {
  display: inline-flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  white-space: normal;
  line-height: 1.6;
}
.option-item.recommended :deep(.el-radio__label),
.option-item.recommended :deep(.el-checkbox__label) {
  font-weight: 600;
}
.opt-text {
  flex: 1;
  min-width: 0;
  word-break: break-word;
}
.rec-badge {
  padding: 0 6px;
  border-radius: 8px;
  background: var(--el-color-success-light-8);
  color: var(--el-color-success);
  font-size: 11px;
  font-weight: 400;
}
.readonly-options li.selected { border-color: var(--el-color-success); background: var(--el-color-success-light-9); }
.selected-badge { margin-left: 6px; color: var(--el-color-success); font-size: 12px; }
.readonly-answer { margin: 8px 0 0; color: var(--el-text-color-regular); line-height: 1.6; white-space: pre-wrap; }
.readonly-answer-label { color: var(--el-text-color-secondary); }
.readonly-answer.skipped { color: var(--el-text-color-secondary); }
.detail-link {
  color: var(--el-color-primary);
  font-size: 12px;
  text-decoration: underline;
  cursor: pointer;
}
.opt-detail {
  color: var(--el-text-color-primary);
  font-size: 13px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
}
:global(.option-detail-dialog) {
  max-width: calc(100vw - 32px);
}
.custom-input { margin-top: 8px; }
.choice-custom-input :deep(.el-input__wrapper) {
  min-height: 40px;
  padding: 0 12px;
  background: var(--el-fill-color-light);
}
.custom-hint {
  margin: 6px 0 0;
  color: var(--el-color-warning);
  font-size: 12px;
  line-height: 1.5;
}

.stepper-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}
/* 「结束对话并补全需求」推到最右，与逐题导航在视觉上分开 */
.end-btn { margin-left: auto; }
.stepper-hint {
  margin: 8px 0 0;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  line-height: 1.6;
}

/* ===== 只读态：历史气泡分组回溯 ===== */
.question-group {
  margin-top: 12px;
  padding: 10px 12px;
  border-left: 3px solid var(--el-color-primary-light-3);
  background: var(--el-color-primary-light-9);
  border-radius: 0 6px 6px 0;
}
.question-group.conflicts { border-left-color: var(--el-color-warning); background: var(--el-color-warning-light-9); }
.question-group.suggestions { border-left-color: var(--el-color-success); background: var(--el-color-success-light-9); }
.question-group h4 {
  margin: 0 0 6px;
  color: var(--el-text-color-primary);
  font-size: 13px;
}
.question-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.question-item {
  padding: 8px 10px;
  border-radius: 6px;
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-lighter);
}
.question-text.readonly { font-size: 13px; }
.readonly-options {
  margin: 6px 0 0;
  padding-left: 18px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  line-height: 1.8;
}
.readonly-options li.recommended { color: var(--el-color-success); }
</style>
