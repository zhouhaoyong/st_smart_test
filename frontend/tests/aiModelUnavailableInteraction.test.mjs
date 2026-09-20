import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const read = path => readFileSync(new URL(path, import.meta.url), 'utf8')
const apiSource = read('../src/api/testWorkbench.js')
const startConfirmSource = read('../src/views/test-workbench/components/RefinementStartConfirm.vue')
const refinementDrawerSource = read('../src/views/test-workbench/components/RequirementRefinementDrawer.vue')
const testCaseGenerateSource = read('../src/views/test-workbench/components/TestCaseGenerateDialog.vue')
const refinementComposableSource = read('../src/views/test-workbench/composables/useRequirementRefinement.js')

const sourceOf = name => {
  const start = apiSource.indexOf(`export const ${name}`)
  assert.notEqual(start, -1, `${name} should exist`)
  const nextExport = apiSource.indexOf('\nexport ', start + 1)
  return apiSource.slice(start, nextExport === -1 ? undefined : nextExport)
}

// 预检错误不经过全局 Toast，统一由当前 AI 弹窗展示。
for (const name of [
  'getWorkbenchRequirementAiModel',
  'getWorkbenchMergeRequirementAiModel',
  'getWorkbenchMergedRequirementAiModel',
  'getWorkbenchTestCaseAiModel',
]) {
  assert.match(sourceOf(name), /skipErrorToast:\s*true/)
}

// 所有当前 AI 入口都复用同一个开始确认组件。
assert.match(refinementDrawerSource, /<RefinementStartConfirm/)
assert.match(testCaseGenerateSource, /<RefinementStartConfirm/)

// 无可用模型时，提示留在弹窗内，并统一跳转到普通用户的“我的模型”列表。
assert.match(startConfirmSource, /v-if="modelLoadError"/)
assert.match(startConfirmSource, /去配置/)
assert.match(startConfirmSource, /useRouter/)
assert.match(startConfirmSource, /ModelAdminModelsMine/)
assert.match(refinementComposableSource, /配置一个已启用且额度可用的模型/)

// 模型调用失败后，继续回答、补充和结束整理都必须先完成模型重试选择。
assert.match(refinementComposableSource, /const retrySelectionRequired = ref\(false\)/)
assert.match(refinementComposableSource, /if \(!firstRoundDone\.value \|\| busy\.value \|\| retrySelectionRequired\.value\) return false/)
assert.match(refinementComposableSource, /if \(busy\.value \|\| !firstRoundDone\.value \|\| retrySelectionRequired\.value\) return/)
assert.match(refinementComposableSource, /if \(busy\.value \|\| !firstRoundDone\.value \|\| retrySelectionRequired\.value \|\| !supplement\) return/)
assert.match(refinementDrawerSource, /:retry-selection-required="retrySelectionRequired"/)
assert.match(testCaseGenerateSource, /:retry-selection-required="retrySelectionRequired"/)
assert.match(refinementComposableSource, /if \(!selectModel\(nextModel\.id\)\)[\s\S]*retrySelectionRequired\.value = false/)

console.log('AI model unavailable interaction test ok')
