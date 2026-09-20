import { computed, nextTick, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getWorkbenchRequirementAiModel,
  saveWorkbenchRequirementAi,
  composeWorkbenchRequirementAiStream,
  compareWorkbenchRequirementAiStream,
  askWorkbenchRequirementAiStream,
} from '@/api/testWorkbench'
import { getAiModelsForFeature } from '@/api/ai'
import { pickPreferredAiModelId } from '@/utils/aiModelPreference'
import { copyToClipboard } from '@/utils/clipboard'

// 默认 API 适配器：对接单条需求 AI 补全接口。
// 合并需求复用同一状态机，只需传入自己的 api 适配器与文案覆盖即可。
// 统一签名：askStream(id, payload, onEvent, signal) / composeStream(id, payload, onEvent, signal) / save(id, payload)
const REQUIREMENT_API = {
  feature: 'test_workbench_requirement_completion',
  getModel: getWorkbenchRequirementAiModel,
  // 一轮追问（流式）：payload = { round, history, answers, initial_content? }
  askStream: askWorkbenchRequirementAiStream,
  // 「结束对话」= AI 在原文基础上修订出补全正文（流式），payload = { history }，仅返回预览内容、不落库
  composeStream: composeWorkbenchRequirementAiStream,
  compareStream: compareWorkbenchRequirementAiStream,
  // 「预览并保存」= 写入用户编辑后的正文（不调用 AI），是整条链路唯一写库的地方
  save: saveWorkbenchRequirementAi,
  // 从资产对象取「原始输入」「发起补全时的初始正文」
  getOriginal: requirement => requirement?.original_content || '',
  getStartContent: requirement => requirement?.original_content || '',
}

// 模型/服务端报错统一以「AI 助手」气泡的形式留在对话流里，不再让界面回退到开始确认页。
// 数据库类内部异常不向用户暴露原文，其余一律回显模型返回的真实错误，便于超管定位。
const formatConversationError = error => {
  const message = String(error?.message || '').trim()
  if (!message || /(?:IntegrityError|foreign key|SQL)/i.test(message)) {
    return '本轮 AI 处理失败：服务内部异常，未能生成回复。'
  }
  return `本轮 AI 处理失败：${message}`
}

// 失败气泡支持原轮重试；连续失败时仍给出排障方向。
const ERROR_HINT_BROKEN = '可重试本次调用；重试仍失败时，请在「管理中心」核对 AI 模型配置或查看服务日志。'
const ERROR_HINT_RESUMABLE = '可重试本次调用；重试可能消耗额度，如反复失败请在「管理中心」核对 AI 模型配置或查看服务日志。'
const MODEL_UNAVAILABLE_MESSAGE = '当前没有可用的 AI 模型，请配置一个已启用且额度可用的模型后再试。'
// 统一取错误业务字段：非流式请求经响应拦截器包成 {code,message,data}，业务字段在 error.data.data；
// 流式请求已把字段扁平化到 error.data 顶层。两种形态归一到同一层再读，避免生成失败误判 retryable。
const errorPayload = error => {
  const root = error?.data
  if (!root || typeof root !== 'object') return {}
  return root.data && typeof root.data === 'object' ? { ...root, ...root.data } : root
}
const retryCandidatesOf = error => {
  const list = errorPayload(error).retry_candidates
  return Array.isArray(list) ? list : []
}
const errorHintFor = (error, firstRoundDone) => {
  if (retryCandidatesOf(error).length) return firstRoundDone ? ERROR_HINT_RESUMABLE : ERROR_HINT_BROKEN
  if (errorPayload(error).quota_exhausted) {
    return '当前模型额度已用完，暂无其他可用模型，请在「管理中心」配置其他可用模型或等待额度恢复后再试。'
  }
  return '当前没有可用的备用模型，请在「管理中心」检查 AI 模型配置后再试。'
}

const normalizeModelLoadError = error => {
  const message = String(error?.data?.message || error?.message || '').trim()
  if (/(?:没有可用|暂无可用).{0,12}模型/.test(message)) return MODEL_UNAVAILABLE_MESSAGE
  return message || MODEL_UNAVAILABLE_MESSAGE
}

// 提交给后端的问答字段白名单：保留后端分配的稳定 ID，并独立记录用户实际选择。
const historyItem = (question, status = 'pending', answer = '', details = {}) => ({
  id: String(question?.id || '').trim() || undefined,
  text: String(question?.text || ''),
  category: question?.category || 'must_confirm',
  type: question?.type || 'open',
  options: Array.isArray(question?.options) ? question.options : [],
  recommended: question?.recommended || '',
  multi: !!question?.multi,
  status,
  answer: String(answer || ''),
  selected_options: Array.isArray(details.selectedOptions) ? details.selectedOptions : [],
  custom_answer: String(details.custom || ''),
  action: details.action === 'skip' ? 'skip' : 'answer',
})

// 仅用于清理旧版本遗留的本地临时记录；AI 补全对话不保存也不恢复。
const SNAPSHOT_PREFIX = 'tw-ai-refine:'

// AI 补全需求的会话状态机：与对话框外壳解耦。
// 交互闭环：追问 → 用户回答（至少一次）→「结束对话」触发 AI 在原文上修订成文（对话流内流式）
//          → 助手消息挂「预览并保存」按钮 →「预览并保存」弹窗（可编辑、可复制）→ 保存后落库。
// **全程无状态**：累积问答由本文件持有（history），每次请求整包回传，后端不落任何过程数据。
export function useRequirementRefinement({ getRequirement, close, emit, api, getScope }) {
  const adapter = { ...REQUIREMENT_API, ...(api || {}) }
  // 「对话式合并」场景没有资产 id：作用域（版本 + 来源需求）随每次请求回传，后端据此重读来源正文。
  const scope = () => getScope?.() || null
  const conversationKind = () => adapter.conversationKind || (scope() ? 'merge' : 'refine')
  const currentId = () => getRequirement()?.id
  const loading = ref(false)
  const streaming = ref(false)
  // 是否已发起过对话（含失败）。用于让界面停留在会话视图：首轮调用失败时也不能退回
  // 「开始 AI 补全」确认页，否则会把错误气泡整块丢掉、用户看不到失败原因。
  const conversationStarted = ref(false)
  // 首轮就失败：一轮都没跑通，隐藏作答区，只留错误气泡与联系超管提示。
  const conversationBroken = ref(false)
  // 首轮是否已成功返回过问题：之后即可提交回答 / 结束对话。
  const firstRoundDone = ref(false)
  // 模型调用失败后的安全闸门：必须选择候选模型并确认原轮重试，才允许继续提交、补充或结束整理。
  const retrySelectionRequired = ref(false)
  const retryModelLoading = ref(false)
  let openSequence = 0
  const composing = ref(false)
  const saving = ref(false)
  const modelInfo = ref(null)
  const modelCandidates = ref([])
  const selectedModelId = ref(null)
  const lastCallGroupId = ref('')
  const modelLoadError = ref('')
  // 原始输入（预览弹窗左侧对照展示 + 字数守恒对比）
  const originalContent = ref('')
  // AI 修订出的正文预览（尚未落库），预览弹窗基于它编辑与保存
  const composedDraft = ref('')
  const comparisonResult = ref(null)
  // 不对应具体问题的用户补充：仅在 AI 暂无新问题时提交，但会随会话传给后续追问与最终整理。
  const supplements = ref([])
  // 后端守恒校验结果 { passed, issues[], missing_lines[], missing_total, metrics{} }：
  // 不通过时预览弹窗醒目告警，保存需二次确认。
  const composeCheck = ref(null)
  // 最新一条挂「预览并保存」按钮的助手消息 id：只有它可点，早前的整理结果按钮置灰
  const composeMsgId = ref('')
  // 累积问答：本状态机**唯一**的会话状态，同时承担原来 open_questions + confirmed_facts
  // + resolved_or_dismissed 三份服务端状态的职责。
  // 每项 { text, category, type, options, recommended, multi, status, answer }
  const history = ref([])
  // 已提交的追问轮数（0 = 尚未提交过回答）。后端会对它做区间收敛。
  const roundNumber = ref(0)
  // 结构化追问：当前这一轮待用户回答的问题（后端返回「上轮遗留未处理 + 本轮新增」的整体列表）。
  // id 是纯前端生成的绑定键（后端已取消问题 id 体系），提交时按问题文本配对回传。
  const activeQuestions = ref([])
  // answerDraft: { [questionId]: { action:'answer'|'skip', selected:[], custom:'' } }
  const answerDraft = ref({})
  // 当前可交互作答的助手消息 id（仅最新一条有待答问题的追问气泡可作答，历史气泡只读）
  const activeQuestionMsgId = ref('')
  // 本次会话内的对话轮次（打开时重新开始，不回放历史会话）
  const messages = ref([])
  const scrollRef = ref(null)

  // 顶部状态栏：只承载「短状态」，绝不显示模型返回的长总结（长总结属于卡片正文）。
  const statusText = ref('')
  const statusType = ref('info')
  const setStatus = (text, type = 'info') => {
    statusText.value = text
    statusType.value = type
  }
  const statusLabel = computed(() => statusText.value || (streaming.value ? 'AI 正在生成回复…' : '正在梳理需求细节'))
  const askContentSections = () => {
    return [{ key: 'ask-prompt', title: 'AI 身份与追问规则', content: String(modelInfo.value?.prompt_preview || ''), markdown: true, open: false }]
      .filter(section => section.content)
  }
  const composeContentSections = () => {
    const content = String(modelInfo.value?.compose_prompt_preview || '')
    return content ? [{ key: 'compose-prompt', title: 'AI 整理规则', content, markdown: true, open: false }] : []
  }
  const comparisonContentSections = () => {
    const content = String(modelInfo.value?.compare_prompt_preview || '')
    return content ? [{ key: 'compare-prompt', title: 'AI 对比规则', content, markdown: true, open: false }] : []
  }
  const generationContentSections = () => {
    const content = String(modelInfo.value?.generation_prompt_preview || '')
    return content ? [{ key: 'generation-prompt', title: 'AI 用例生成规则', content, markdown: true, open: false }] : []
  }
  const contentSectionTitle = key => ({
    'compose-prompt': 'AI 整理规则',
    'generation-prompt': 'AI 用例生成规则',
  }[key] || 'AI 身份与追问规则')
  const patchPromptSection = (messageIndex, content, key = 'ask-prompt') => {
    if (messageIndex === null || messageIndex === undefined || !content) return
    const message = messages.value[messageIndex]
    if (!message) return
    const sections = [...(message.contentSections || [])]
    const section = sections.find(item => item.key === key)
    if (section) section.content = String(content)
    else sections.unshift({ key, title: contentSectionTitle(key), content: String(content), markdown: true, open: false })
    patchMessage(messageIndex, { contentSections: sections })
  }

  // ---------- 清理旧版本地临时记录 ----------
  const snapshotKey = () => {
    const current = scope()
    if (current) return `${SNAPSHOT_PREFIX}merge:${current.version_id}:${(current.source_ids || []).join('-')}`
    const id = currentId()
    return id ? `${SNAPSHOT_PREFIX}req:${id}` : ''
  }
  const clearSnapshot = () => {
    try {
      const key = snapshotKey()
      if (key) localStorage.removeItem(key)
    } catch {
      /* ignore */
    }
  }
  const GROUP_META = [
    { key: 'must_confirm', label: '必须确认' },
    { key: 'conflicts', label: '冲突待确认' },
    { key: 'missing_scenarios', label: '遗漏场景' },
    { key: 'suggestions', label: '建议补充' },
  ]
  // 把后端返回的扁平结构化问题按分类归组，供卡片/作答面板分节展示（空组不展示）。
  const groupQuestions = questions => {
    const source = Array.isArray(questions) ? questions : []
    return GROUP_META.map(meta => ({
      ...meta,
      items: source.filter(question => (question.category || 'must_confirm') === meta.key),
    })).filter(group => group.items.length)
  }
  // 为一批问题初始化逐题作答草稿：默认「作答」动作、未选、无自定义。
  const buildAnswerDraft = questions => {
    const draft = {}
    for (const question of questions || []) {
      if (!question?.id) continue
      draft[question.id] = { action: 'answer', selected: [], custom: '' }
    }
    return draft
  }
  // 用户在结构化面板里改动某一题（选项/自定义/跳过）时，整块替换以触发响应式更新。
  const onAnswerChange = (id, patch) => {
    if (!id) return
    const current = answerDraft.value[id] || { action: 'answer', selected: [], custom: '' }
    answerDraft.value = { ...answerDraft.value, [id]: { ...current, ...patch } }
  }
  // 结算本轮作答：把当前展示的每道题落成一条问答记录。
  // 返回 { turn, answered }：turn 是当前展示问题的全量记录（含仍未处理的 pending），
  // answered 是本轮新处理（回答/跳过）的子集，仅用于装配后端的 latest_user_reply。
  const settleAnswers = () => {
    const turn = []
    const answered = []
    for (const question of activeQuestions.value) {
      const draft = answerDraft.value[question.id] || {}
      if (draft.action === 'skip') {
        const item = historyItem(question, 'skipped', '', { action: 'skip' })
        turn.push(item)
        answered.push(item)
        continue
      }
      const custom = String(draft.custom || '').trim()
      // 自定义输入具有排他性：一旦填写，本题只取自定义意见，预设选项一律清空、不计入，
      // 使 selected_options 与前端选项置灰（model-value 置空）的表现一致，避免二者相互矛盾。
      const selected = custom ? [] : (Array.isArray(draft.selected) ? draft.selected.filter(Boolean) : [])
      const text = custom || selected.join('；')
      if (text) {
        const item = historyItem(question, 'answered', text, { selectedOptions: selected, custom })
        turn.push(item)
        answered.push(item)
      } else {
        // 未触碰：保持待处理，继续挂在下一轮界面上。
        turn.push(historyItem(question, 'pending', '', { selectedOptions: selected, custom }))
      }
    }
    return { turn, answered }
  }
  const captureActiveAnswerSnapshot = () => {
    if (!activeQuestionMsgId.value) return
    const answerSnapshot = {}
    for (const question of activeQuestions.value) {
      const draft = answerDraft.value[question.id] || {}
      const custom = String(draft.custom || '').trim()
      // 与结算口径一致：填了自定义输入则不再回显预设选项，保证快照不残留矛盾数据。
      const selected = custom ? [] : (Array.isArray(draft.selected) ? draft.selected.filter(Boolean) : [])
      if (draft.action === 'skip' || selected.length || custom) {
        answerSnapshot[question.id] = { action: draft.action || 'answer', selected, custom }
      }
    }
    const messageIndex = messages.value.findIndex(message => message.id === activeQuestionMsgId.value)
    if (messageIndex >= 0) patchMessage(messageIndex, { answerSnapshot })
  }
  // 累积问答 = 此前已处理的（answered/skipped，永不重问） + 本轮展示问题的最新状态。
  // 后端据此推导 pending / resolved_or_dismissed，不需要任何服务端状态。
  const mergeHistory = turn => [...history.value.filter(item => item.status !== 'pending'), ...turn]

  const canStart = computed(() => !!modelInfo.value && !!selectedModelId.value)
  const busy = computed(() => streaming.value || composing.value || saving.value)
  // 最近一条「有效追问气泡」：跳过整理成文气泡，以及报错/被用户停止的气泡。
  // 报错或停止只是本轮未产出，不应把上一轮已达成的收敛结论一起作废、让用户无法再结束对话。
  const lastQuestionRound = computed(() => {
    for (let index = messages.value.length - 1; index >= 0; index -= 1) {
      const message = messages.value[index]
      if (!message || message.role !== 'assistant') continue
      // 已经整理成功过：收尾入口交给该气泡的「预览并保存」，不再回头点「结束对话」。
      if (message.kind === 'compose' || message.kind === 'compare') {
        if (message.error || message.stopped || message.pending) continue
        return null
      }
      if (message.pending || message.error || message.stopped) continue
      return message
    }
    return null
  })
  // 后端确定性收敛判定：最近一条有效追问气泡的 ready_for_preview 为真（阻塞类问题已全部回答/跳过，或已提交过 1 轮）。
  const readyToEnd = computed(() => Boolean(lastQuestionRound.value?.readyForPreview))
  // 「结束对话并补全需求」可点条件：首轮已跑通、空闲、且后端判定已可收敛。
  const hasUserContribution = computed(() => (
    supplements.value.length > 0
    || history.value.some(item => item.status === 'answered' || item.status === 'skipped')
  ))
  const canEnd = computed(() => {
    if (!firstRoundDone.value || busy.value || retrySelectionRequired.value) return false
    if (conversationKind() === 'test_case') {
      return hasUserContribution.value
        && !activeQuestions.value.some(item => ['must_confirm', 'conflicts'].includes(item.category))
    }
    return hasUserContribution.value && readyToEnd.value
  })
  // 「提交回答」可点条件：首轮已跑通、空闲、且用户至少在卡片内作答了一题（不再有游离补充框）。
  const canSend = computed(() => {
    if (!firstRoundDone.value || busy.value || retrySelectionRequired.value) return false
    const settled = settleAnswers()
    if (!settled.answered.length) return false
    // test_case 与 refine 一致：作答后即可「提交回答」进入下一轮追问，未答的关键项留到下一轮继续问。
    return true
  })
  // 气泡内「结束对话并补全需求」按钮只挂在最近一条、且 AI 判定可结束的追问气泡下，避免每条旧气泡都冒一颗。
  const endActionMsgId = computed(() => (canEnd.value ? lastQuestionRound.value?.id || '' : ''))

  // 助手正文导语：分组问题已由下方结构化区块单独渲染，后端 reply 不再把分组问题拼进正文，
  // 故不再按「【」截断（否则进度文案自身含全角【】时会误删后半句，包括收尾引导语）。
  const assistantLead = content => String(content || '').trim()

  // 本轮用户回答的可读摘要，用于对话流内即时展示用户气泡（严格回显用户在卡片内的逐题选择/输入）。
  const summarizeTurn = answered => {
    const lines = answered.map(item => {
      if (item.status === 'skipped') return `· 「${item.text}」——已跳过`
      const selected = item.selected_options?.length
        ? `用户选择：${item.selected_options.join('、')}`
        : ''
      const custom = item.custom_answer ? `用户输入：${item.custom_answer}` : ''
      const fallback = item.answer && !selected && !custom
        ? `${item.type === 'open' ? '用户输入' : '用户回答'}：${item.answer}`
        : ''
      return `· 「${item.text}」：${[selected, custom, fallback].filter(Boolean).join('；') || '已回答'}`
    })
    if (lines.length) return `【本轮逐题回答】\n${lines.join('\n')}`
    return '（继续完善需求）'
  }

  // 吸底策略：默认吸底；用户手动上滑后暂停自动吸底，滚回底部附近或提交新一轮时恢复。
  const stickBottom = ref(true)
  const stickTop = ref(true)
  const scrollToBottom = (force = false) => {
    if (!force && !stickBottom.value) return
    nextTick(() => scrollRef.value?.setScrollTop?.(999999))
  }
  const scrollToTopManually = () => {
    stickTop.value = true
    stickBottom.value = false
    nextTick(() => scrollRef.value?.setScrollTop?.(0))
  }
  const scrollToBottomManually = () => {
    stickBottom.value = true
    scrollToBottom(true)
  }
  const onScroll = ({ scrollTop }) => {
    const wrap = scrollRef.value?.wrapRef
    if (!wrap) return
    stickTop.value = scrollTop <= 40
    stickBottom.value = wrap.scrollHeight - wrap.clientHeight - scrollTop <= 40
  }

  // 复制：统一走剪贴板，带降级方案；仅在该轮输出结束后调用（模板已用 messageCopyable 守卫）。
  const copyText = async text => {
    const value = String(text || '').trim()
    if (!value) return
    try {
      if (!await copyToClipboard(value)) throw new Error('clipboard unavailable')
      ElMessage.success('已复制')
    } catch {
      ElMessage.error('复制失败，请手动选择复制')
    }
  }
  // 复制开关：用户输入在提交时即已定稿，复制不依赖 AI 是否回复完成，始终可复制；
  // 助手气泡内容边生成边追加，仍需等本轮输出结束（pending 结束）后才可复制。
  const messageCopyable = message => {
    if (message.role === 'user') return true
    return !message.pending
  }
  const patchMessage = (index, patch) => {
    const current = messages.value[index]
    if (current) messages.value[index] = { ...current, ...patch }
  }

  // 由后端回传的 model 块装配「用量条模型行」所需数据：别名优先取候选模型（含友好别名），
  // 模型类型（平台/我的）以候选为准、缺失时回退额度作用域；额度取本轮调用后快照。
  const buildModelMeta = model => {
    if (!model?.id) return null
    const candidate = modelCandidates.value.find(item => Number(item.id) === Number(model.id))
    const scope = candidate?.scope || (model?.quota?.scope === 'personal' ? 'personal' : 'platform')
    return {
      alias: candidate?.name || model.name || '未命名模型',
      scope,
      quota: model.quota || null,
    }
  }

  const applyAssistant = (index, assistant, clientElapsedMs = null, userIndex = null) => {
    // 后端返回扁平结构化问题列表 questions =「上轮遗留未处理 + 本轮新增」，前端整体替换卡片列表；
    // ID 由后端分配并跨轮次保留，只有最新一条追问气泡可交互，历史气泡只读。
    const questions = (Array.isArray(assistant?.questions) ? assistant.questions : [])
      .map(question => ({ ...question, id: String(question?.id || '').trim() }))
      .filter(question => question.id)
    const assistantId = messages.value[index]?.id || ''
    activeQuestions.value = questions
    answerDraft.value = buildAnswerDraft(questions)
    activeQuestionMsgId.value = questions.length ? assistantId : ''
    // 新问题以「待处理」并入累积问答，保证下一轮请求里后端还能看到它们。
    history.value = mergeHistory(questions.map(question => historyItem(question, question.status || 'pending', question.answer || '')))
    roundNumber.value = Number(assistant?.round || roundNumber.value)
    firstRoundDone.value = true
    const streamedReasoning = messages.value[index]?.reasoning || ''
    patchMessage(index, {
      content: assistantLead(assistant?.reply || ''),
      reasoning: streamedReasoning || assistant?.reasoning_content || '',
      questions,
      groups: groupQuestions(questions),
      blockingRemaining: Number(assistant?.blocking_remaining || 0),
      round: Number(assistant?.round || 0),
      maxRounds: Number(assistant?.max_rounds || 0),
      pending: false,
      reasoningOpen: false, // 思考结束：默认收起
      outputOpen: true, // 输出完成：默认展开
      readyForPreview: !!assistant?.ready_for_preview, // 供气泡内「结束对话并补全需求」按钮判断
      supplementEnabled: !questions.length,
      // 本轮用量（公共用量条展示）：后端归一后的 token { input/output/cache/total_tokens }，拿不到为 null
      usage: assistant?.usage || null,
      // 本轮实际所用模型及调用后额度（用量条模型行展示），拿不到为 null
      modelMeta: buildModelMeta(assistant?.model),
      // 本轮耗时统一取前端计时（发起→流式结束），与后端 elapsed_ms 解耦避免时间对不上
      clientElapsedMs,
    })
    if (assistant?.call_group_id) lastCallGroupId.value = assistant.call_group_id
    if (assistant?.model?.id) {
      modelInfo.value = {
        ...modelInfo.value,
        id: assistant.model.id,
        name: assistant.model.name || modelInfo.value?.name,
        supports_reasoning: assistant.model.supports_reasoning,
        reasoning_status: assistant.model.supports_reasoning ? 'supported' : modelInfo.value?.reasoning_status,
      }
    }
    const nextAction = conversationKind() === 'merge' ? '整理合并需求' : conversationKind() === 'test_case' ? '开始生成测试用例' : '整理补全需求'
    if (questions.length) setStatus(`AI 已补充 ${questions.length} 个待确认项，请继续作答`, 'info')
    else if (assistant?.done) setStatus(`追问已完成，可${nextAction}`, 'success')
    else if (assistant?.ready_for_preview) setStatus(`需求已梳理完成，可${nextAction}`, 'success')
    else setStatus(`本轮追问完成，可继续作答或${nextAction}`, 'success')
  }

  const handleStreamEvent = (index, event, userIndex = null) => {
    if (!event) return
    if (event.type === 'prompt') {
      patchPromptSection(userIndex, event.content || '', messages.value[userIndex]?.compose ? 'compose-prompt' : 'ask-prompt')
    } else if (event.type === 'reasoning_delta') {
      const current = messages.value[index]
      patchMessage(index, {
        reasoning: `${current?.reasoning || ''}${event.delta || ''}`,
        ...(current?.reasoningDone ? {} : { reasoningOpen: true }),
      })
      scrollToBottom()
    } else if (event.type === 'delta') {
      // 首个正文增量到达后自动收起一次；后续推理增量只追加内容，不再改变展开状态。
      const current = messages.value[index]
      if (!current?.reasoningDone && (current?.reasoning || '').length) {
        patchMessage(index, { reasoningOpen: false, reasoningDone: true })
      }
      // 整理成文（compose）阶段：模型的输出增量即最终 Markdown 正文，实时追加到气泡里显示进度，
      // 避免长文档整理时界面长时间只剩 spinner、看起来像卡死/无响应；首个增量到达即结束 pending。
      // 追问阶段（raw_mode=false，输出是 JSON 信封）不在此回显，交由 complete 事件渲染结构化问题。
      if (current?.kind === 'compose') {
        patchMessage(index, {
          pending: false,
          content: `${current?.content || ''}${event.delta || ''}`,
        })
        scrollToBottom()
      }
    } else if (event.type === 'call_start' || event.type === 'model_start' || event.type === 'parse') {
      const fallback = event.type === 'model_start' ? 'AI 正在处理中…' : statusLabel.value
      setStatus(event.message || fallback, 'primary')
    }
  }

  const newCallGroupId = () => {
    const suffix = globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`
    return `tw-${suffix}`
  }
  const selectModel = modelId => {
    const selected = modelCandidates.value.find(item => Number(item.id) === Number(modelId))
    if (!selected) return false
    selectedModelId.value = Number(selected.id)
    modelInfo.value = { ...modelInfo.value, ...selected }
    return true
  }
  const withModelSelection = (payload, callGroupId) => ({
    ...payload,
    ...(selectedModelId.value ? { selected_model_id: selectedModelId.value } : {}),
    ...(callGroupId ? { call_group_id: callGroupId } : {}),
  })
  const selectedModelSection = () => {
    const model = modelCandidates.value.find(item => Number(item.id) === Number(selectedModelId.value)) || modelInfo.value
    if (!model?.id) return []
    const scopeLabel = model.scope === 'platform' ? '平台模型' : '我的模型'
    return [{
      key: 'selected-model',
      title: '本轮实际使用模型',
      content: `${scopeLabel}｜${model.name || '未命名模型'}｜${model.model || ''}`,
      markdown: false,
      open: false,
    }]
  }

  // 停止生成：中断当前流式请求（前端断开连接，后端本轮结果作废）
  const streamAbort = ref(null)
  const stopStream = () => {
    if (streamAbort.value) streamAbort.value.abort()
  }

  // 一轮追问。mode='start' 为首轮，mode='send' 为提交回答，mode='supplement' 为自由补充。
  const runStream = async ({ mode, content = '', callGroupId = '' }) => {
    // 快照本轮提交前的状态，用户主动停止或调用失败时原样恢复，让他可以直接重试。
    const prevQuestions = activeQuestions.value
    const prevDraft = answerDraft.value
    const prevMsgId = activeQuestionMsgId.value
    const prevHistory = history.value
    const prevSupplements = supplements.value

    let payload
    let displayContent
    let submittedTurn = []
    if (mode === 'start') {
      payload = { round: 0, history: [], answers: [] }
      // 合并链路没有资产正文可改；单需求链路把用户在确认页改过的原文一并落库。
      if (!scope()) payload.initial_content = content
      displayContent = scope() ? '请将所选的原始需求合并为一份合并需求。' : content
      history.value = []
      roundNumber.value = 0
    } else if (mode === 'supplement') {
      const supplement = String(content || '').trim()
      supplements.value = [...supplements.value, supplement]
      payload = {
        round: roundNumber.value + 1,
        history: history.value,
        answers: [],
        supplements: supplements.value,
        supplement,
      }
      displayContent = `【补充内容】\n${supplement}`
    } else {
      const { turn, answered } = settleAnswers()
      submittedTurn = turn
      history.value = mergeHistory(turn)
      payload = {
        round: roundNumber.value + 1,
        history: history.value,
        answers: answered,
        supplements: supplements.value,
      }
      displayContent = summarizeTurn(answered)
    }
    // 新一轮开始：作答面板先清空（新问题到达后由 applyAssistant 重新填充），避免旧问题误提交。
    captureActiveAnswerSnapshot()
    activeQuestions.value = []
    activeQuestionMsgId.value = ''
    const stamp = Date.now()
    messages.value.push({
      id: `u-${stamp}`, role: 'user', content: displayContent, contentOpen: false,
      initial: mode === 'start',
      answerDetails: submittedTurn,
      answerDetailsOpen: false, // 「本轮回答详情」默认收起，用户可整行点击展开

      contentSections: [...askContentSections(), ...selectedModelSection()],
      sourceTitle: conversationKind() === 'merge' ? '本次合并来源' : '本次来源需求',
      sourceSnapshots: mode === 'start' && scope()?.source_snapshots
        ? (scope()?.source_snapshots || []).map(source => ({ ...source, expanded: false }))
        : [],
    })
    const userIndex = messages.value.length - 1
    messages.value.push({ id: `a-${stamp}`, role: 'assistant', content: '', reasoning: '', reasoningOpen: true, reasoningDone: false, outputOpen: true, questions: [], groups: [], pending: true })
    const assistantIndex = messages.value.length - 1
    const controller = new AbortController()
    streamAbort.value = controller
    streaming.value = true
    conversationStarted.value = true
    setStatus('AI 正在生成回复…', 'primary')
    stickBottom.value = true // 新一轮：强制回到底部
    scrollToBottom(true)
    // 前端计时起点：与气泡内实时计时同源（发起模型调用即开始），成功产出后冻结为本轮耗时
    const startedAt = Date.now()
    const attemptedRound = Number(payload.round || 0)
    const effectiveCallGroupId = callGroupId || newCallGroupId()
    try {
      const result = await adapter.askStream(
        currentId(),
        withModelSelection({ ...(scope() || {}), ...payload }, effectiveCallGroupId),
        event => handleStreamEvent(assistantIndex, event, userIndex),
        controller.signal,
      )
      patchPromptSection(userIndex, result.assistant?.prompt || '')
      applyAssistant(assistantIndex, result.assistant, Date.now() - startedAt, userIndex)
    } catch (err) {
      // 用户主动停止：本轮作废、恢复输入框内容与作答面板，不当作错误提示
      if (controller.signal.aborted || err?.name === 'AbortError') {
        patchMessage(assistantIndex, {
          pending: false,
          content: '已停止生成，本轮回复未采纳。',
          questions: [],
          groups: [],
          stopped: true,
          round: attemptedRound,
          clientElapsedMs: Date.now() - startedAt,
        })
        setStatus('已停止本轮生成，可继续补充或重新提交', 'info')
        if (mode === 'send' || mode === 'supplement') {
          history.value = prevHistory
          if (mode === 'supplement') supplements.value = supplements.value.slice(0, -1)
          activeQuestions.value = prevQuestions
          answerDraft.value = prevDraft
          activeQuestionMsgId.value = prevMsgId
        }
      } else {
        // 模型报错以 AI 气泡形式留在对话流（含真实报错原文），界面不回退到开始确认页。
        const retryCandidates = retryCandidatesOf(err)
        // 仅当确有其他可切换模型时才要求重新选模型；没有候选就不锁死会话，
        // 用户仍可基于已确认信息结束对话或刷新可用模型，避免单模型/额度耗尽时彻底卡死。
        retrySelectionRequired.value = retryCandidates.length > 0
        patchMessage(assistantIndex, {
          pending: false,
          content: formatConversationError(err),
          questions: [],
          groups: [],
          error: true,
          errorHint: errorHintFor(err, firstRoundDone.value),
          retryable: retryCandidates.length > 0,
          retryAction: {
            type: 'ask', mode, content,
            callGroupId: err?.data?.call_group_id || effectiveCallGroupId,
            modelId: selectedModelId.value,
            modelName: modelInfo.value?.name || '',
            currentModel: modelInfo.value ? { ...modelInfo.value } : null,
            retryContext: firstRoundDone.value && mode !== 'start'
              ? { questions: prevQuestions, draft: prevDraft, messageId: prevMsgId, history: prevHistory, supplements: prevSupplements }
              : null,
            retryCandidates,
            platformModelUnavailable: Boolean(err?.data?.platform_model_unavailable),
            quotaExhausted: Boolean(err?.data?.quota_exhausted),
            currentModelScope: err?.data?.current_model_scope || '',
            currentModelName: err?.data?.current_model_name || modelInfo.value?.name || '',
          },
          round: attemptedRound,
          clientElapsedMs: Date.now() - startedAt,
        })
        if (firstRoundDone.value) {
          // 已提交的问题保持只读；重试时由 retryContext 恢复原始提交快照，避免用户误以为仍可编辑。
          activeQuestions.value = []
          answerDraft.value = {}
          activeQuestionMsgId.value = ''
        } else {
          // 首轮就失败：本次对话无法继续，作答区一并收起。
          conversationBroken.value = true
        }
        setStatus(firstRoundDone.value ? '本轮补全失败' : 'AI 补全未能开始', 'danger')
      }
    } finally {
      streaming.value = false
      streamAbort.value = null
      scrollToBottom()
    }
  }

  const start = async () => {
    if (!canStart.value) return
    // 「对话式合并」没有资产 id，作用域即入口参数；单需求链路必须已有资产。
    if (!scope() && !currentId()) return
    conversationBroken.value = false
    await runStream({ mode: 'start', content: scope() ? '' : adapter.getStartContent(getRequirement()) })
  }

  const send = async () => {
    if (busy.value || !firstRoundDone.value || retrySelectionRequired.value) return
    const { turn, answered } = settleAnswers()
    if (!answered.length) {
      ElMessage.warning('请至少回答一个问题后再提交')
      return
    }
    // test_case 走与 refine 一致的多轮追问：提交回答只推进一轮追问，不直接生成用例。
    // 追问收敛（某轮不再有关键确认项）后，再由「确认并开始生成测试用例」触发 endConversation 生成。
    await runStream({ mode: 'send' })
  }

  const sendSupplement = async value => {
    const supplement = String(value || '').trim()
    if (busy.value || !firstRoundDone.value || retrySelectionRequired.value || !supplement) return
    // 补充内容继续进入追问流程；测试用例生成由「确认并开始生成测试用例」单独触发。
    await runStream({ mode: 'supplement', content: supplement })
  }

  // 「结束对话并补全需求」：让 AI 在原文基础上修订出补全后的正文（对话流内流式展示真实进度），
  // 完成后在助手气泡挂「预览并保存」按钮。整理仅返回预览内容、不落库；反复整理时只认最新一条按钮。
  const endConversation = async ({ retry = false, callGroupId = '' } = {}) => {
    if (!retry && !canEnd.value) return
    if (conversationKind() === 'test_case') {
      if (!retry) {
        const { turn } = settleAnswers()
        if (turn.some(item => ['must_confirm', 'conflicts'].includes(item.category) && item.status === 'pending')) {
          ElMessage.warning('请先回答或跳过全部关键确认项')
          return
        }
        history.value = mergeHistory(turn)
      }
      const generate = adapter.generateTestCases
      if (typeof generate !== 'function') {
        emit('preflight-complete', { history: history.value, supplements: supplements.value })
        close()
        return
      }
      captureActiveAnswerSnapshot()
      activeQuestions.value = []
      activeQuestionMsgId.value = ''
      const stamp = Date.now()
      messages.value.push({
        id: `u-generate-${stamp}`, role: 'user', content: '开始生成测试用例', contentOpen: false,
        contentSections: [...generationContentSections(), ...selectedModelSection()],
      })
      const assistantId = `generate-${stamp}`
      messages.value.push({
        id: assistantId, role: 'assistant', content: '', reasoning: '', reasoningOpen: true, reasoningDone: false,
        outputOpen: true, groups: [], pending: true, kind: 'test_case_generate',
      })
      const index = messages.value.length - 1
      const startedAt = Date.now()
      composing.value = true
      streaming.value = true
      setStatus('AI 正在生成测试用例…', 'primary')
      stickBottom.value = true
      scrollToBottom(true)
      const effectiveCallGroupId = callGroupId || lastCallGroupId.value || newCallGroupId()
      try {
        const result = await generate(currentId(), withModelSelection({
          ...(scope() || {}),
          history: history.value,
          supplements: supplements.value,
        }, effectiveCallGroupId))
        const total = Array.isArray(result?.test_cases) ? result.test_cases.length : 0
        if (!total) throw new Error('AI 未生成有效用例，请调整需求内容后重试')
        // 部分来源失败或内容被截断时给出一次性提醒：已生成的照常保留，失败/截断来源可单独重试。
        const generateNotes = []
        if (Array.isArray(result?.failed_sources) && result.failed_sources.length) {
          generateNotes.push(`${result.failed_sources.length} 个来源生成失败（${result.failed_sources.map(item => item.title).join('、')}），可稍后单独重试`)
        }
        if (Array.isArray(result?.truncated_sources) && result.truncated_sources.length) {
          generateNotes.push(`${result.truncated_sources.length} 个来源内容较长可能未生成完整（${result.truncated_sources.join('、')}），建议拆分需求后重试`)
        }
        patchMessage(index, {
          content: `已生成 ${total} 条测试用例，请查看后勾选并保存。${generateNotes.length ? `\n注意：${generateNotes.join('；')}。` : ''}`,
          pending: false,
          action: 'case-preview',
          generatedResult: result,
          clientElapsedMs: Date.now() - startedAt,
        })
        if (generateNotes.length) ElMessage.warning(generateNotes.join('；'))
        patchPromptSection(messages.value.length - 2, result?.generation_prompt || '', 'generation-prompt')
        composeMsgId.value = assistantId
        setStatus('测试用例已生成，等待查看并保存', 'success')
      } catch (error) {
        const generatePayload = errorPayload(error)
        const retryCandidates = retryCandidatesOf(error)
        // 仅当确有其他可切换模型时才要求重新选模型；没有候选就不锁死会话，
        // 用户仍可基于已确认信息结束对话或刷新可用模型，避免单模型/额度耗尽时彻底卡死。
        retrySelectionRequired.value = retryCandidates.length > 0
        patchMessage(index, {
          content: formatConversationError(error),
          pending: false,
          error: true,
          errorHint: errorHintFor(error, firstRoundDone.value),
          retryable: retryCandidates.length > 0,
          retryAction: {
            type: 'generate',
            callGroupId: generatePayload.call_group_id || effectiveCallGroupId,
            modelId: selectedModelId.value,
            modelName: modelInfo.value?.name || '',
            currentModel: modelInfo.value ? { ...modelInfo.value } : null,
            retryCandidates,
            platformModelUnavailable: Boolean(generatePayload.platform_model_unavailable),
            quotaExhausted: Boolean(generatePayload.quota_exhausted),
            currentModelScope: generatePayload.current_model_scope || '',
            currentModelName: generatePayload.current_model_name || modelInfo.value?.name || '',
          },
          clientElapsedMs: Date.now() - startedAt,
        })
        setStatus('生成测试用例失败，可重试', 'danger')
      } finally {
        composing.value = false
        streaming.value = false
        scrollToBottom(true)
      }
      return
    }
    const isMergeConversation = conversationKind() === 'merge'
    const endLabel = isMergeConversation ? '结束对话并整理合并需求' : '结束对话并补全需求'
    // 进入整理阶段：把当前展示的问题状态结算进累积问答（未答的按 pending 留痕，
    // 后端会在提示词里明示「未确认，请按现有信息推断」），随后收起作答面板。
    if (!retry) {
      const { turn } = settleAnswers()
      history.value = mergeHistory(turn)
    }
    captureActiveAnswerSnapshot()
    activeQuestions.value = []
    activeQuestionMsgId.value = ''
    // 点击「结束对话并补全需求」本质上是用户发起的一条指令，先作为用户消息显示，
    // 让对话流「有来有回」；随后再挂 AI 整理正文的助手气泡。
    const composeStamp = Date.now()
    messages.value.push({
      id: `u-compose-${composeStamp}`, role: 'user', content: endLabel, contentOpen: false, compose: true,
      contentSections: [...composeContentSections(), ...selectedModelSection()],
    })
    const composeUserIndex = messages.value.length - 1
    const assistantId = `compose-${composeStamp}`
    messages.value.push({
      id: assistantId, role: 'assistant', content: '', reasoning: '', reasoningOpen: true, reasoningDone: false,
      outputOpen: true, groups: [], pending: true, kind: 'compose',
    })
    const index = messages.value.length - 1
    const controller = new AbortController()
    streamAbort.value = controller
    composing.value = true
    streaming.value = true // 复用流式态：显示停止按钮、禁用输入框
    setStatus(isMergeConversation ? 'AI 正在整合来源需求并编排正文…' : 'AI 正在基于原文修订补全正文…', 'primary')
    stickBottom.value = true
    scrollToBottom(true)
    // 前端计时起点：与气泡内实时计时同源，成功产出后冻结为本步耗时
    const startedAt = Date.now()
    const effectiveCallGroupId = callGroupId || lastCallGroupId.value || newCallGroupId()
    try {
      const result = await adapter.composeStream(
        currentId(),
        withModelSelection({ ...(scope() || {}), history: history.value, supplements: supplements.value }, effectiveCallGroupId),
        event => handleStreamEvent(index, event, composeUserIndex),
        controller.signal,
      )
      const markdown = String(result?.compose?.markdown_content || '').trim()
      if (!markdown) throw new Error(isMergeConversation ? 'AI 未返回合并后的正文，请补充更多信息后重试' : 'AI 未返回补全后的正文，请补充更多信息后重试')
      composedDraft.value = markdown
      composeCheck.value = result?.compose?.check || null
      composeMsgId.value = assistantId
      const failed = composeCheck.value && composeCheck.value.passed === false
      patchMessage(index, {
        pending: false,
        reasoningOpen: false,
        content: failed
          ? `已生成${isMergeConversation ? '合并需求正文' : '补全正文'}，但系统检出来源内容可能有缺失，请点击下方「预览并保存」核对告警后再保存。`
          : isMergeConversation
            ? '已整合来源需求并完成正文编排。「预览并保存」可查看、编辑并保存正文；「预览并对比」可核对原始内容、最终正文与本次问答的纳入情况。'
            : '已在原文基础上完成补全。「预览并保存」可查看、编辑并保存正文；「预览并对比」可核对原始内容、最终正文与本次问答的纳入情况。',
        groups: [],
        action: 'preview-save',
        // 整理成文这一步同样展示用量；轮次沿用对话已进行的追问轮数
        round: roundNumber.value,
        usage: result?.compose?.usage || null,
        modelMeta: buildModelMeta(result?.compose?.model),
        // 耗时统一取前端计时（发起→流式结束），与后端 elapsed_ms 解耦，避免前后端对不上
        clientElapsedMs: Date.now() - startedAt,
      })
      const resultLabel = isMergeConversation ? '合并需求正文' : '补全正文'
      setStatus(failed ? `${resultLabel}已生成，但守恒校验未通过，请预览核对` : `${resultLabel}已生成，请预览并保存`, failed ? 'warning' : 'success')
    } catch (err) {
      if (controller.signal.aborted || err?.name === 'AbortError') {
        patchMessage(index, {
          pending: false,
          content: `已停止${isMergeConversation ? '合并整理' : '补全'}，可继续补充后再次${endLabel}。`,
          groups: [],
          stopped: true,
          round: roundNumber.value,
          clientElapsedMs: Date.now() - startedAt,
        })
        setStatus(`已停止${isMergeConversation ? '合并整理' : '补全'}，可继续补充`, 'info')
      } else {
        const retryCandidates = retryCandidatesOf(err)
        // 仅当确有其他可切换模型时才要求重新选模型；没有候选就不锁死会话，
        // 用户仍可基于已确认信息结束对话或刷新可用模型，避免单模型/额度耗尽时彻底卡死。
        retrySelectionRequired.value = retryCandidates.length > 0
        patchMessage(index, {
          pending: false,
          content: formatConversationError(err),
          groups: [],
          error: true,
          errorHint: errorHintFor(err, firstRoundDone.value),
          retryable: retryCandidates.length > 0,
          retryAction: {
            type: 'compose',
            callGroupId: err?.data?.call_group_id || effectiveCallGroupId,
            modelId: selectedModelId.value,
            modelName: modelInfo.value?.name || '',
            currentModel: modelInfo.value ? { ...modelInfo.value } : null,
            retryCandidates,
            platformModelUnavailable: Boolean(err?.data?.platform_model_unavailable),
            quotaExhausted: Boolean(err?.data?.quota_exhausted),
            currentModelScope: err?.data?.current_model_scope || '',
            currentModelName: err?.data?.current_model_name || modelInfo.value?.name || '',
          },
          round: roundNumber.value,
          clientElapsedMs: Date.now() - startedAt,
        })
        setStatus(isMergeConversation ? '合并失败' : '补全失败', 'danger')
      }
    } finally {
      streaming.value = false
      composing.value = false
      streamAbort.value = null
      scrollToBottom()
    }
  }

  const compare = async () => {
    if (busy.value || !composedDraft.value.trim() || typeof adapter.compareStream !== 'function') return
    try {
      await ElMessageBox.confirm('本次对比将消耗 1 次 AI 额度，用于核对本次问答和补充是否纳入最终正文。是否继续？', '确认预览并对比', {
        type: 'warning', confirmButtonText: '开始对比', cancelButtonText: '取消',
      })
    } catch { return }
    const stamp = Date.now()
    messages.value.push({
      id: `u-compare-${stamp}`, role: 'user', content: '预览并对比本次最终结果', contentOpen: false,
      contentSections: [...comparisonContentSections(), ...selectedModelSection()],
      sourceTitle: conversationKind() === 'merge' ? '本次合并来源' : '本次来源需求',
      sourceSnapshots: conversationKind() === 'merge' && scope()?.source_snapshots
        ? (scope()?.source_snapshots || []).map(source => ({ ...source, expanded: false }))
        : [],
    })
    const userIndex = messages.value.length - 1
    const assistantId = `compare-${stamp}`
    messages.value.push({ id: assistantId, role: 'assistant', content: '', reasoning: '', reasoningOpen: true, reasoningDone: false, outputOpen: true, groups: [], pending: true, kind: 'compare' })
    const index = messages.value.length - 1
    const controller = new AbortController()
    streamAbort.value = controller
    streaming.value = true
    setStatus('AI 正在核对本次结果…', 'primary')
    stickBottom.value = true
    scrollToBottom(true)
    const startedAt = Date.now()
    try {
      const result = await adapter.compareStream(
        currentId(),
        withModelSelection({
          ...(scope() || {}),
          history: history.value,
          supplements: supplements.value,
          markdown_content: composedDraft.value,
        }, lastCallGroupId.value || newCallGroupId()),
        event => handleStreamEvent(index, event, userIndex), controller.signal,
      )
      const comparison = result?.comparison || {}
      comparisonResult.value = comparison
      patchPromptSection(userIndex, comparison.prompt || '', 'compare-prompt')
      patchMessage(index, {
        pending: false, reasoningOpen: false, content: comparison.overview || '已完成本次结果核对。',
        action: 'comparison-preview', comparisonResult: comparison, groups: [], round: roundNumber.value,
        usage: comparison.usage || null, modelMeta: buildModelMeta(comparison.model),
        clientElapsedMs: Date.now() - startedAt,
      })
      setStatus('结果核对完成，可查看对比概要', 'success')
    } catch (err) {
      // 用户主动停止：与追问/整理口径一致，显示「已停止」而非「失败」；对比只读、不落库。
      if (controller.signal.aborted || err?.name === 'AbortError') {
        patchMessage(index, {
          pending: false, content: '已停止本次结果核对。', groups: [], stopped: true,
          round: roundNumber.value, clientElapsedMs: Date.now() - startedAt,
        })
        setStatus('已停止本次结果核对', 'info')
      } else {
        patchMessage(index, { pending: false, content: formatConversationError(err), groups: [], error: true, clientElapsedMs: Date.now() - startedAt })
        setStatus('结果核对失败', 'danger')
      }
    } finally {
      streaming.value = false
      streamAbort.value = null
      scrollToBottom()
    }
  }

  const openTestCasePreview = result => {
    if (!Array.isArray(result?.test_cases) || !result.test_cases.length) return
    emit('case-preview', result)
  }

  const refreshRetryCandidates = async messageId => {
    const failed = messages.value.find(message => message.id === messageId)
    const action = failed?.retryAction
    if (!action || !adapter.feature || retryModelLoading.value) return
    retryModelLoading.value = true
    try {
      const result = await getAiModelsForFeature(adapter.feature, { skipErrorToast: true })
      // 刷新即"重新获取最新可用模型 + 重新核对各模型（含当轮失败模型）的实时额度"：
      // 不再排除当轮失败模型，否则提额/额度恢复后的当前模型永远回不到清单，用户无法重新选中重试。
      const candidates = Array.isArray(result?.candidates) ? result.candidates : []
      modelCandidates.value = candidates
      const index = messages.value.findIndex(message => message.id === messageId)
      if (index >= 0) {
        patchMessage(index, {
          retryable: candidates.length > 0,
          retryAction: { ...action, retryCandidates: candidates },
        })
      }
    } catch (error) {
      ElMessage.error(error?.message || '刷新可用模型失败，请检查模型配置后重试')
    } finally {
      retryModelLoading.value = false
    }
  }

  const retry = async retrySelection => {
    if (busy.value) return
    const messageId = typeof retrySelection === 'object' ? retrySelection?.messageId : retrySelection
    const nextModelId = retrySelection?.modelId
    // 只允许重试对话流中最新一条失败气泡：旧气泡的重试会用其快照回退 history/supplements，
    // 覆盖用户在其后的作答，造成上下文倒退。此处作为兜底，防止绕过按钮置灰直接触发。
    if (messageId !== messages.value[messages.value.length - 1]?.id) return
    const failed = messages.value.find(message => message.id === messageId)
    const action = failed?.retryAction
    if (!action || !nextModelId) return
    const retryCandidates = Array.isArray(action.retryCandidates) ? action.retryCandidates : []
    const nextModel = retryCandidates.find(candidate => Number(candidate.id) === Number(nextModelId))
    if (!nextModel) {
      ElMessage.warning('所选模型当前不可用，请重新选择')
      return
    }
    try {
      const scopeText = nextModel.scope === 'platform' ? '平台模型' : '我的模型'
      if (!retrySelection?.confirmed) await ElMessageBox.confirm(`将使用${scopeText}「${nextModel.name}」重新发起一次模型调用，可能产生模型侧消耗，是否继续？`, '确认重试', {
        type: 'warning',
        confirmButtonText: '确认重试',
        cancelButtonText: '暂不重试',
      })
    } catch {
      return
    }
    if (!modelCandidates.value.some(candidate => Number(candidate.id) === Number(nextModel.id))) {
      modelCandidates.value = retryCandidates
    }
    if (!selectModel(nextModel.id)) {
      ElMessage.warning('所选模型当前不可用，请重新选择')
      return
    }
    retrySelectionRequired.value = false
    retryModelLoading.value = false
    if (action.type === 'compose' || action.type === 'generate') {
      await endConversation({ retry: true, callGroupId: action.callGroupId })
      return
    }
    if (action.retryContext) {
      activeQuestions.value = action.retryContext.questions || []
      answerDraft.value = action.retryContext.draft || {}
      activeQuestionMsgId.value = action.retryContext.messageId || ''
      history.value = action.retryContext.history || history.value
      supplements.value = action.retryContext.supplements || supplements.value
    }
    await runStream({ mode: action.mode, content: action.content, callGroupId: action.callGroupId })
  }

  // 「预览并保存」弹窗点保存：写入用户编辑后的正文并落库为待确认，不调用 AI。
  const save = async value => {
    const content = String(value?.markdown_content ?? value ?? composedDraft.value ?? '').trim()
    if (!content) {
      ElMessage.warning('需求正文不能为空')
      return
    }
    saving.value = true
    try {
      const result = await adapter.save(currentId(), { ...(scope() || {}), markdown_content: content, title: value?.title })
      clearSnapshot()
      emit('previewed', result)
      close()
    } finally {
      saving.value = false
    }
  }

  const reset = () => {
    conversationStarted.value = false
    conversationBroken.value = false
    firstRoundDone.value = false
    messages.value = []
    history.value = []
    roundNumber.value = 0
    statusText.value = ''
    statusType.value = 'info'
    modelInfo.value = null
    modelCandidates.value = []
    selectedModelId.value = null
    lastCallGroupId.value = ''
    modelLoadError.value = ''
    stickBottom.value = true
    stickTop.value = true
    originalContent.value = ''
    composedDraft.value = ''
    comparisonResult.value = null
    supplements.value = []
    composeCheck.value = null
    composeMsgId.value = ''
    composing.value = false
    saving.value = false
    activeQuestions.value = []
    answerDraft.value = {}
    activeQuestionMsgId.value = ''
    retrySelectionRequired.value = false
    retryModelLoading.value = false
  }

  // 关闭前二次确认：一旦发起过补全（已调用 LLM）或正在生成，提示对话不会保存
  const handleBeforeClose = async done => {
    // 首轮就失败：一轮都没跑通、没有任何可丢失的内容，直接关闭，不再多问一次。
    if (conversationBroken.value) {
      clearSnapshot()
      done()
      return
    }
    const llmTouched = streaming.value || composing.value || firstRoundDone.value || messages.value.length > 0
    if (!llmTouched) {
      clearSnapshot()
      done()
      return
    }
    try {
      await ElMessageBox.confirm(
        '关闭后，对话记录将不再保留，是否确认关闭？',
        '关闭确认',
        { type: 'warning', confirmButtonText: '确认关闭', cancelButtonText: '取消' },
      )
      stopStream() // 关闭同时中断进行中的流式请求
      clearSnapshot() // 用户确认放弃：本地暂存一并清除，下次打开是干净的新对话
      done()
    } catch {
      /* 用户取消关闭，保持弹窗 */
    }
  }

  // 打开对话框：清理旧版遗留记录并重置会话，始终从开始页进入。
  const open = async () => {
    const sequence = ++openSequence
    reset()
    clearSnapshot()
    originalContent.value = adapter.getOriginal(getRequirement())
    loading.value = true
    try {
      modelInfo.value = await adapter.getModel(currentId())
      if (sequence !== openSequence) return
      if (adapter.feature) {
        const result = await getAiModelsForFeature(adapter.feature, {
          skipErrorToast: true,
          skipSuccessToast: true,
        })
        if (sequence !== openSequence) return
        modelCandidates.value = Array.isArray(result?.candidates) ? result.candidates : []
      }
      if (sequence !== openSequence) return
      // 有功能标识时，候选接口已经完成权限、启用和额度筛选；没有候选不能回退到未校验的当前模型。
      if (adapter.feature && !modelCandidates.value.length) {
        // 预检详情可能仍返回旧模型，但它已不在最新可用候选中时不能继续展示旧快照。
        modelInfo.value = null
        modelLoadError.value = MODEL_UNAVAILABLE_MESSAGE
      }
      if (!adapter.feature && !modelCandidates.value.length && modelInfo.value?.id) modelCandidates.value = [modelInfo.value]
      const preferredModelId = pickPreferredAiModelId(
        modelCandidates.value,
        null,
      )
      selectModel(preferredModelId || (!adapter.feature ? modelInfo.value?.id : null))
    } catch (error) {
      if (sequence !== openSequence) return
      modelInfo.value = null
      modelCandidates.value = []
      modelLoadError.value = normalizeModelLoadError(error)
    } finally {
      if (sequence === openSequence) loading.value = false
    }
  }

  return {
    loading,
    streaming,
    composing,
    saving,
    conversationStarted,
    conversationBroken,
    firstRoundDone,
    modelInfo,
    modelCandidates,
    selectedModelId,
    modelLoadError,
    messages,
    history,
    supplements,
    roundNumber,
    scrollRef,
    statusType,
    statusLabel,
    canStart,
    canEnd,
    canSend,
    retrySelectionRequired,
    retryModelLoading,
    readyToEnd,
    stickBottom,
    stickTop,
    originalContent,
    composedDraft,
    comparisonResult,
    composeCheck,
    composeMsgId,
    endActionMsgId,
    activeQuestions,
    answerDraft,
    activeQuestionMsgId,
    onAnswerChange,
    selectModel,
    groupQuestions,
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
  }
}
