import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const read = path => readFileSync(new URL(path, import.meta.url), 'utf8')
const pickerSource = read('../src/components/AiModelPickerDialog.vue')
const panelSource = read('../src/views/test-workbench/components/AiModelSelectionPanel.vue')
const settingsSource = read('../src/components/AiGenerationModePickerDialog.vue')
const settingsPanelSource = read('../src/components/AiGenerationModePickerPanel.vue')
const batchSource = read('../src/components/BatchInterfaceCaseGenerationDialog.vue')

// 用例生成模型：生成设置弹窗内选，且生成设置弹窗兼作生成前确认
assert.match(settingsSource, /<AiModelPickerDialog/)
assert.match(settingsPanelSource, /用例生成模型/)
assert.match(settingsSource, /@pick-model="modelPickerVisible = true"/)
assert.match(settingsPanelSource, /modelTitleText/)
assert.match(batchSource, /<AiGenerationModePickerDialog/)
assert.match(batchSource, /selectedModelId/)

assert.match(pickerSource, /title="选择模型"/)
assert.match(pickerSource, /确认选择/)
assert.match(pickerSource, /require-explicit-selection/)
assert.match(pickerSource, /update:selectedModelId/)

// 当前模型摘要必须跟随下拉选中的候选模型实时更新
assert.match(panelSource, /findAiModel\(props\.modelCandidates, displaySelectedModelId\.value\)/)
assert.match(panelSource, /class="model-summary-label"/)
assert.match(panelSource, /class="model-summary-main"/)
assert.match(panelSource, /class="model-summary-capabilities"/)
assert.match(panelSource, /class="model-summary-alias"/)
assert.match(panelSource, /class="model-summary-name"/)
assert.match(panelSource, /class="model-summary-connectivity"/)
assert.match(panelSource, /class="model-summary-reasoning"/)
// 摘要整行不换行；别名和模型名称各自固定宽度并以省略号收尾
assert.match(panelSource, /.model-summary\s*\{[^}]*flex-wrap:\s*nowrap;/s)
assert.match(panelSource, /.model-summary\s*\{[^}]*overflow:\s*hidden;/s)
assert.doesNotMatch(panelSource, /overflow-x:\s*(auto|scroll)/)
assert.match(panelSource, /.model-summary-label\s*\{[^}]*white-space:\s*nowrap;/s)
assert.match(panelSource, /.model-summary-alias,\s*.model-summary-name\s*\{[^}]*text-overflow:\s*ellipsis;/s)
assert.match(panelSource, /.model-summary-alias\s*\{[^}]*flex:\s*0 0 140px;/s)
assert.match(panelSource, /.model-summary-name\s*\{[^}]*flex:\s*0 0 160px;/s)

console.log('AI 导入模型选择与生成确认回归校验通过')
