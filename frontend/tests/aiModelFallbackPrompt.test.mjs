import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const composable = readFileSync(
  new URL('../src/views/test-workbench/composables/useRequirementRefinement.js', import.meta.url),
  'utf8',
)

// 平台模型运行时失败时，详细说明保留在对话流；重试必须由用户选择模型。
assert.match(composable, /platformModelUnavailable: Boolean\(err\?\.data\?\.platform_model_unavailable\)/)
assert.doesNotMatch(composable, /const personalRetryModel = action\.platformModelUnavailable/)
assert.match(composable, /const nextModelId = retrySelection\?\.modelId/)
assert.match(composable, /modelId: selectedModelId\.value/)
assert.match(composable, /selectModel\(nextModel\.id\)/)

console.log('ai model fallback prompt test ok')
