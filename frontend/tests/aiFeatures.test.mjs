import assert from 'node:assert/strict'
import {
  aiFeatureLabels,
  resolveAiFeatureLabel,
  resolveAiFunctionFilter,
  resolveAiFunctionLabel,
} from '../src/utils/aiUsageLabels.js'

// 当前平台按业务能力统一展示 AI 功能名称，并将历史动作归一到统一功能筛选值。
assert.equal(aiFeatureLabels.test_workbench_requirement_completion, 'AI需求补全')
assert.equal(resolveAiFeatureLabel('test_workbench_requirement_merge'), 'AI需求合并')
assert.equal(resolveAiFeatureLabel('test_workbench_test_case_generate'), 'AI生成测试用例')
assert.equal(resolveAiFunctionLabel({ action: 'tw_requirement_merge_refinement' }), 'AI需求合并')
assert.equal(resolveAiFunctionFilter('AI需求补全'), 'test_workbench_requirement_completion')
assert.equal(resolveAiFunctionLabel({ feature: 'unknown' }), '—')

console.log('aiFeatures tests ok')
