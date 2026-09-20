const FEATURE_LABELS = Object.freeze({
  test_workbench_requirement_completion: 'AI需求补全',
  test_workbench_requirement: 'AI需求补全',
  test_workbench_structure: 'AI需求补全',
  requirement_completion: 'AI需求补全',
  requirement_refinement: 'AI需求补全',
  requirement_structure: 'AI需求补全',
  test_workbench_requirement_merge: 'AI需求合并',
  test_workbench_test_case_generate: 'AI生成测试用例',
  test_workbench_test_case: 'AI生成测试用例',
  test_case_generate: 'AI生成测试用例',
  ui_generate_cases: 'AI生成测试用例',
  api_interface_case_generate: '接口批量生成用例',
})

const ACTION_FEATURES = Object.freeze({
  tw_requirement_refinement: 'test_workbench_requirement_completion',
  tw_requirement_compose: 'test_workbench_requirement_completion',
  tw_requirement_compose_continue: 'test_workbench_requirement_completion',
  tw_requirement_result_comparison: 'test_workbench_requirement_completion',
  tw_requirement_structure: 'test_workbench_requirement_completion',
  tw_requirement_merge_refinement: 'test_workbench_requirement_merge',
  tw_requirement_merge_compose: 'test_workbench_requirement_merge',
  tw_requirement_merge_compose_continue: 'test_workbench_requirement_merge',
  tw_requirement_merge_result_comparison: 'test_workbench_requirement_merge',
  tw_requirement_merge_preview: 'test_workbench_requirement_merge',
  tw_test_case_preflight: 'test_workbench_test_case_generate',
  tw_test_case_generate: 'test_workbench_test_case_generate',
  ui_generate_cases: 'test_workbench_test_case_generate',
  api_interface_case_generate: 'api_interface_case_generate',
})

const LEGACY_ACTION_LABELS = Object.freeze({
  analyze: '历史动作：智能分析',
  reanalyze: '历史动作：重新分析',
  translate: '历史动作：翻译',
  ui_analyze_requirement: '历史动作：需求分析',
  ui_analyze_requirement_coverage_repair: '历史动作：需求覆盖率修复',
  ui_generate_cases_coverage_repair: '历史动作：用例覆盖率修复',
  ui_generate_script_set: '历史动作：脚本集生成',
  ui_repair_script_set: '历史动作：脚本集修复',
  ui_generate_cases_json_repair: '历史动作：用例 JSON 修复',
})

const AUDIT_FUNCTION_RULES = Object.freeze([
  { needles: ['需求合并', '合并需求', 'AI需求合并', 'AI合并'], label: 'AI需求合并' },
  { needles: ['需求AI补全', 'AI补全需求', 'AI需求补全', 'AI补全追问'], label: 'AI需求补全' },
  { needles: ['AI生成测试用例', 'AI用例生成'], label: 'AI生成测试用例' },
  { needles: ['接口批量生成用例'], label: '接口批量生成用例' },
])

const FUNCTION_FILTER_KEYS = Object.freeze({
  AI需求补全: 'test_workbench_requirement_completion',
  AI需求合并: 'test_workbench_requirement_merge',
  AI生成测试用例: 'test_workbench_test_case_generate',
  接口批量生成用例: 'api_interface_case_generate',
})

export const aiFeatureLabels = FEATURE_LABELS
export const aiActionFeatures = ACTION_FEATURES
export const aiActionLabels = Object.freeze(
  Object.fromEntries([
    ...Object.keys(ACTION_FEATURES),
    ...Object.keys(LEGACY_ACTION_LABELS),
  ].map(action => [action, resolveAiFunctionLabel({ action })])),
)

export function resolveAiFunctionLabel({ feature = '', action = '' } = {}) {
  const featureKey = String(feature || '').trim()
  const actionKey = String(action || '').trim()
  if (FEATURE_LABELS[featureKey]) return FEATURE_LABELS[featureKey]
  const mappedFeature = ACTION_FEATURES[actionKey]
  if (mappedFeature && FEATURE_LABELS[mappedFeature]) return FEATURE_LABELS[mappedFeature]
  if (LEGACY_ACTION_LABELS[actionKey]) return LEGACY_ACTION_LABELS[actionKey]
  return actionKey ? `其他：${actionKey}` : '—'
}

export function resolveAiAuditFunctionLabel(description) {
  const text = String(description || '').trim()
  if (!text) return ''
  const matched = AUDIT_FUNCTION_RULES.find(rule => rule.needles.some(needle => text.includes(needle)))
  return matched?.label || ''
}

export function resolveAiFunctionFilter(value) {
  const text = String(value || '').trim()
  return FUNCTION_FILTER_KEYS[text] || ACTION_FEATURES[text] || text
}

export function resolveAiFeatureLabel(feature) {
  const key = String(feature || '').trim()
  return FEATURE_LABELS[key] || (key ? `其他：${key}` : '—')
}
