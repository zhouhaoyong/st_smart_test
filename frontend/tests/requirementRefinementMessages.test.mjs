import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const drawer = readFileSync(
  new URL('../src/views/test-workbench/components/RequirementRefinementDrawer.vue', import.meta.url),
  'utf8',
)
const answerBox = readFileSync(
  new URL('../src/views/test-workbench/components/RefinementAnswerBox.vue', import.meta.url),
  'utf8',
)
const messageCard = readFileSync(
  new URL('../src/views/test-workbench/components/RefinementMessageCard.vue', import.meta.url),
  'utf8',
)
const composable = readFileSync(
  new URL('../src/views/test-workbench/composables/useRequirementRefinement.js', import.meta.url),
  'utf8',
)
const requirementPage = readFileSync(
  new URL('../src/views/test-workbench/components/RequirementManagementPage.vue', import.meta.url),
  'utf8',
)
const mergedPage = readFileSync(
  new URL('../src/views/test-workbench/pages/WorkbenchMergedRequirementPage.vue', import.meta.url),
  'utf8',
)

assert.match(drawer, /v-model="saveVisible"/)
assert.match(drawer, /:rule-title="workflow\.ruleTitle"/)
assert.match(answerBox, /v-for="action in actionItems"/)
assert.match(answerBox, /emit\('action', action\.key\)/)
assert.match(messageCard, /message\.reasoningOpen \? '收起' : '展开'/)

// 追问过程不入库：关闭前必须明确提示对话不会保存
assert.match(composable, /const llmTouched = streaming\.value \|\| composing\.value/)
assert.match(composable, /关闭后，对话记录将不再保留，是否确认关闭？/)
// 会话状态由前端本地持有并随请求回传，后端无状态
assert.match(composable, /const history = ref\(\[\]\)/)
assert.match(composable, /const mergeHistory = /)
assert.doesNotMatch(composable, /\bsessionId\b|ai-sessions/)

assert.match(requirementPage, /<RequirementRefinementDrawer[\s\S]*:scope="mergeScope"[\s\S]*@previewed="onMergePreviewed"/)
assert.match(requirementPage, /@click="openMerge"/)
assert.doesNotMatch(requirementPage, /\bpreviewWorkbenchRequirementMerge\b|\bsaveWorkbenchMergedRequirement\b/)
assert.match(mergedPage, /<RequirementRefinementDrawer[\s\S]*:scope="aiScope"[\s\S]*:workflow="mergedAiWorkflow"[\s\S]*@previewed="onAiPreviewed"/)
assert.doesNotMatch(mergedPage, /\bpreviewWorkbenchRequirementMerge\b|\bsaveWorkbenchMergedRequirement\b/)

// Test-case generation keeps the actual generation prompt visible and preserves
// settled answers with the historical question card.
assert.match(composable, /AI 用例生成规则/)
assert.match(composable, /contentSections: generationContentSections\(\)/)
assert.match(messageCard, /本次来源需求/)
assert.doesNotMatch(messageCard, /v-if="message\.sourceSnapshots\.length > 1"/)
assert.match(composable, /answerSnapshot/)
assert.match(messageCard, /:answer-snapshot="message\.answerSnapshot \|\| \{\}"/)

console.log('requirement refinement message and capability reuse test ok')
