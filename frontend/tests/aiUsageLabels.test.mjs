import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolveAiAuditFunctionLabel, resolveAiFunctionFilter, resolveAiFunctionLabel } from '../src/utils/aiUsageLabels.js'

assert.equal(resolveAiFunctionLabel({ feature: 'test_workbench_requirement_completion' }), 'AI需求补全')
assert.equal(resolveAiFunctionLabel({ feature: 'test_workbench_requirement_merge' }), 'AI需求合并')
assert.equal(resolveAiFunctionLabel({ feature: 'test_workbench_test_case_generate' }), 'AI生成测试用例')
assert.equal(resolveAiFunctionLabel({ feature: 'api_interface_case_generate' }), '接口批量生成用例')
assert.equal(resolveAiFunctionLabel({ action: 'tw_requirement_merge_refinement' }), 'AI需求合并')
assert.equal(resolveAiFunctionLabel({ action: 'ui_generate_script_set' }), '历史动作：脚本集生成')
assert.equal(resolveAiFunctionLabel({ action: 'future_action_code' }), '其他：future_action_code')
assert.equal(resolveAiFunctionFilter('接口批量生成用例'), 'api_interface_case_generate')
assert.equal(resolveAiFunctionFilter('tw_requirement_merge_refinement'), 'test_workbench_requirement_merge')
assert.equal(resolveAiFunctionFilter('legacy_action'), 'legacy_action')
assert.equal(resolveAiAuditFunctionLabel('API测试-接口批量生成用例：模型调用成功'), '接口批量生成用例')
assert.equal(resolveAiAuditFunctionLabel('工作台-需求合并整理成文：模型调用成功'), 'AI需求合并')
assert.equal(resolveAiAuditFunctionLabel('普通操作：保存成功'), '')

const auditSource = readFileSync(new URL('../../backend/services/ai_service/_shared.py', import.meta.url), 'utf8')
const usageSource = readFileSync(new URL('../src/views/admin/AiUsage.vue', import.meta.url), 'utf8')
const auditPageSource = readFileSync(new URL('../src/views/AuditLogs.vue', import.meta.url), 'utf8')
assert.match(auditSource, /"api_interface_case_generate": "接口批量生成用例"/)
assert.match(auditSource, /"test_workbench_requirement_completion": "AI需求补全"/)
assert.match(auditSource, /"test_workbench_requirement_merge": "AI需求合并"/)
assert.match(auditSource, /"test_workbench_test_case_generate": "AI生成测试用例"/)
assert.match(auditSource, /"analyze": "历史动作：智能分析"/)
assert.match(usageSource, /功能分布/)
assert.match(usageSource, /label="功能"/)
const statCardRule = usageSource.match(/\.stats-left \.stat-card\s*\{[^}]+\}/)?.[0] || ''
assert.match(statCardRule, /background:\s*#fff/)
assert.match(auditPageSource, /resolveAiAuditFunctionLabel/)

console.log('AI 用量与审计功能命名回归校验通过')
