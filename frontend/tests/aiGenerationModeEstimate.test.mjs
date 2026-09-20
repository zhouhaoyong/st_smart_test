import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const read = path => readFileSync(new URL(path, import.meta.url), 'utf8')
const modePickerSource = read('../src/components/AiGenerationModePickerDialog.vue')
const modePickerPanelSource = read('../src/components/AiGenerationModePickerPanel.vue')
const batchSource = read('../src/components/BatchInterfaceCaseGenerationDialog.vue')

// 生成模式卡片明确展示单接口预计数量范围，避免批量总数被误解为固定配额
assert.match(modePickerPanelSource, /class="mode-picker-option-estimate">\{\{ mode\.estimate \}\}<\/span>/)
assert.match(batchSource, /value: 'main'[\s\S]*?estimate: '每个接口 1 条基础用例'/)
assert.match(batchSource, /value: 'normal'[\s\S]*?estimate: '通常每个接口约 3～5 条用例'/)
assert.match(batchSource, /value: 'full'[\s\S]*?estimate: '通常每个接口约 5～8 条用例'/)
assert.match(batchSource, /value: 'main'[\s\S]*?desc: '由系统按接口定义生成一条基础请求用例。'/)
assert.match(modePickerSource, /预计约 \$\{cases\} 个用例 · 消耗 \$\{aiCalls\} 次 AI 配额次数/)
assert.match(modePickerSource, /预计 \$\{cases\} 个用例 · 不消耗 AI 配额次数/)

console.log('AI 用例生成模式预计范围文案回归校验通过')
