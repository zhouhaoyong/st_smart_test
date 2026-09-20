import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const usageSource = readFileSync(new URL('../src/views/admin/AiUsage.vue', import.meta.url), 'utf8')
const quotaStatsSource = readFileSync(new URL('../src/views/admin/components/UserQuotaStatsDialog.vue', import.meta.url), 'utf8')

assert.match(usageSource, /<el-table-column label="模型来源"[^>]*>[\s\S]*modelScopeLabel\(row\)/)
assert.match(usageSource, /<el-table-column label="模型" prop="model" width="200" show-overflow-tooltip>/)
assert.match(usageSource, /<el-table-column label="模型来源" width="140" align="center">/)
assert.match(usageSource, /<el-table-column label="功能" prop="action" width="210" show-overflow-tooltip>/)
assert.match(usageSource, /:model-scope="usageStatsModelScope"/)
assert.match(usageSource, /const usageStatsModelScope = ref\(''\)/)
assert.match(usageSource, /usageStatsModelScope\.value = modelScopeOf\(row\)/)
assert.match(quotaStatsSource, /modelScope: \{ type: String, default: '' \}/)
assert.match(quotaStatsSource, /activeTab\.value = props\.modelScope === 'personal' \? 'personal' : 'platform'/)

const scopeToolbarRule = usageSource.match(/\.scope-toolbar\s*\{[^}]+\}/)?.[0] || ''
assert.match(scopeToolbarRule, /display:\s*grid/)
assert.match(scopeToolbarRule, /grid-template-columns:\s*280px\s+minmax\(0,\s*1fr\)/)
assert.match(usageSource, /class="scope-group scope-data-group"/)
assert.match(usageSource, /class="scope-group scope-model-group"/)
const modelScopeRule = usageSource.match(/\.scope-model-group\s*\{[^}]+\}/)?.[0] || ''
assert.match(modelScopeRule, /grid-column:\s*2/)
const scopeLabelRule = usageSource.match(/\.scope-label\s*\{[^}]+\}/)?.[0] || ''
assert.match(scopeLabelRule, /font-size:\s*14px/)
const scopeSwitchRule = usageSource.match(/\.scope-switch :deep\(\.el-radio-button__inner\)\s*\{[^}]+\}/)?.[0] || ''
assert.match(scopeSwitchRule, /padding:\s*8px\s+18px/)
assert.match(scopeSwitchRule, /font-size:\s*14px/)
assert.match(usageSource, /\.stats-filter-bar :deep\(\.el-input__wrapper\)[\s\S]*?min-height:\s*34px/)
assert.match(usageSource, /\.stats-filter-bar :deep\(\.el-select__wrapper\)[\s\S]*?min-height:\s*34px/)
assert.match(usageSource, /\.stats-filter-bar :deep\(\.el-button\)[\s\S]*?font-size:\s*14px/)
assert.doesNotMatch(usageSource, /stat-help-button/)
assert.doesNotMatch(usageSource, /InfoFilled/)
assert.doesNotMatch(usageSource, /metricHelpVisible|metricHelpKey|metricHelp|openMetricHelp|metric-help-content/)

console.log('AI 用量模型归属回归校验通过')
