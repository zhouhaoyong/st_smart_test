import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const source = readFileSync(
  new URL('../src/views/test-workbench/components/RequirementPreviewDrawer.vue', import.meta.url),
  'utf8',
)
const listSource = readFileSync(
  new URL('../src/views/test-workbench/components/RequirementManagementPage.vue', import.meta.url),
  'utf8',
)
const previewSource = readFileSync(
  new URL('../src/views/test-workbench/components/RequirementPreviewDrawer.vue', import.meta.url),
  'utf8',
)
const answerBoxSource = readFileSync(
  new URL('../src/views/test-workbench/components/RefinementAnswerBox.vue', import.meta.url),
  'utf8',
)
const refinementDrawerSource = readFileSync(
  new URL('../src/views/test-workbench/components/RequirementRefinementDrawer.vue', import.meta.url),
  'utf8',
)
const messageCardSource = readFileSync(
  new URL('../src/views/test-workbench/components/RefinementMessageCard.vue', import.meta.url),
  'utf8',
)
const questionGroupsSource = readFileSync(
  new URL('../src/views/test-workbench/components/RefinementQuestionGroups.vue', import.meta.url),
  'utf8',
)
const apiSource = readFileSync(
  new URL('../../backend/api/v1/endpoints/test_workbench_routers/requirements.py', import.meta.url),
  'utf8',
)
const refinementServiceSource = [
  'normalize.py',
  'refine.py',
  'synthesize.py',
  '_shared.py',
].map(file => readFileSync(new URL(`../../backend/services/requirement_ai_service/${file}`, import.meta.url), 'utf8')).join('\n')
const refinementPromptSource = readFileSync(
  new URL('../../backend/docs/prompt/requirement_refinement.md', import.meta.url),
  'utf8',
)
const prdSource = readFileSync(new URL('../../docs/测试工作台_产品说明.md', import.meta.url), 'utf8')
const designSource = readFileSync(new URL('../../docs/测试工作台_设计说明.md', import.meta.url), 'utf8')
const providerSource = [
  '_shared.py',
  'openai_compat.py',
].map(file => readFileSync(new URL(`../../backend/llm/providers/${file}`, import.meta.url), 'utf8')).join('\n')

assert.doesNotMatch(source, /ElMessage\.success\('需求已确认'\)/)
assert.match(source, /await ElMessageBox\.confirm\([\s\S]*确认后，该补全需求可作为 AI 生成测试用例的来源。/)
assert.match(source, /确认后，该原始需求可参与合并并作为 AI 生成测试用例的来源。/)
assert.match(listSource, /class="toolbar-form"/)
assert.match(listSource, /withCount\('AI 合并'/)
assert.match(listSource, /\.list-toolbar \{[^}]*flex-shrink: 0;[^}]*margin-bottom: 12px;/)
assert.match(listSource, /const statuses = \[\{ label: '待确认', value: 'draft' \}/)
assert.match(listSource, /<el-form-item label="状态">/)
assert.match(listSource, /statusLabel = status => \(\{ draft: '待确认', confirmed: '已确认' \}/)
assert.match(previewSource, /const statusLabel = status => \(\{ draft: '待确认', confirmed: '已确认' \}/)
assert.match(apiSource, /was_confirmed = requirement\.confirm_status == "confirmed"/)
// 原始需求只有一份正文可编辑（补全正文归补全需求），因此正文变更即回退，仅改标题不回退
assert.match(apiSource, /original_changed = data\.original_content is not None and data\.original_content != requirement\.original_content/)
assert.match(apiSource, /原始需求不支持编辑补全正文，请在补全需求中编辑/)
assert.match(apiSource, /status_reverted = body_changed and was_confirmed/)
assert.match(apiSource, /if status_reverted:\s*requirement\.confirm_status = "draft"/)
assert.match(apiSource, /需求已回退为待确认，请重新确认后再用于合并或生成用例/)
assert.match(prdSource, /待确认 → 已确认/)
assert.match(designSource, /回退为待确认/)
assert.match(answerBoxSource, /class="answer-composer"/)
assert.match(answerBoxSource, /class="composer-toolbar"/)
assert.match(answerBoxSource, /class="composer-submit"/)
assert.match(answerBoxSource, /AiStopStreamButton v-else @confirm="emit\('stop'\)"/)
// 终态动作收敛为一个：「结束对话并补全需求」，预览改由 AI 气泡内的按钮触发
assert.match(refinementDrawerSource, /import \{ ArrowDown, ArrowUp \} from '@element-plus\/icons-vue'/)
assert.match(refinementDrawerSource, /:end-action-id="endActionMsgId"/)
assert.match(refinementDrawerSource, /:end-label="workflow\.endActionLabel"/)
assert.doesNotMatch(refinementDrawerSource, /key: 'compose'|key: 'preview'/)
assert.match(answerBoxSource, /import \{ Promotion \} from '@element-plus\/icons-vue'/)
assert.match(answerBoxSource, /:icon="Promotion"/)
assert.doesNotMatch(answerBoxSource, /CircleClose|\bTop\b/)
assert.match(messageCardSource, /v-html="renderMarkdown\(message\.content\)"/)
assert.match(messageCardSource, /const isMarkdown = content =>/)
assert.match(refinementDrawerSource, /endActionLabel: '结束对话并补全需求'/)
assert.match(refinementDrawerSource, /endActionLabel: '结束对话并整理合并需求'/)
assert.match(designSource, /结束对话并整理成合并正文/)
// 追问无状态化：问题编号由前端本地生成，后端不再有 id 体系；累积状态从前端回传的 history 推导
assert.match(refinementPromptSource, /首轮（`round=0`）：逐项完成适用维度审查，一次性列出所有独立且有测试价值的问题/)
assert.match(refinementPromptSource, /信息诉求相同或高度相似时不得新增/)
assert.match(refinementPromptSource, /不得对已澄清项换措辞重复追问/)
assert.doesNotMatch(refinementPromptSource, /最多 5 个问题/)
assert.doesNotMatch(refinementPromptSource, /resolved_question_ids/)
assert.match(refinementServiceSource, /def normalize_history\(/)
assert.match(refinementServiceSource, /def history_pending\(/)
assert.match(refinementServiceSource, /def build_ask_context\(/)
assert.match(refinementServiceSource, /context\["resolved_or_dismissed"\] = history_resolved_digest\(history\)/)
assert.doesNotMatch(refinementServiceSource, /session\.|merge_confirmed_facts|QUESTION_ID_PATTERN/)
assert.match(questionGroupsSource, /v-for="question in group\.items"/)
assert.match(providerSource, /DEFAULT_LLM_TIMEOUT_SECONDS = 600/)
assert.doesNotMatch(providerSource, /DEFAULT_LLM_STREAM_IDLE_TIMEOUT_SECONDS/)
assert.match(providerSource, /deadline = loop\.time\(\) \+ timeout/)
assert.match(providerSource, /timeout=remaining/)
assert.match(providerSource, /AI模型响应超时（10分钟）/)
// 整理成文只返回草稿：流式端点内不写业务数据，也不回写原始需求正文
assert.match(apiSource, /async def compose_requirement_ai_stream[\s\S]*await db\.rollback\(\)/)
assert.doesNotMatch(refinementServiceSource, /requirement\.markdown_content = markdown/)
assert.match(refinementServiceSource, /def check_compose_preservation\(/)

console.log('requirement confirmation toast test ok')
