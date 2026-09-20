import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { getAssertionOperatorLabel } from '../src/utils/assertionOperators.js'

const read = (path) => readFileSync(new URL(path, import.meta.url), 'utf8')

const report = read('../src/views/Reports.vue')
const debug = read('../src/components/DebugPanel.vue')
const assertionDisplay = read('../src/components/AssertionDiffTable.vue')
const assertionEditor = read('../src/components/RequestConfigTabs.vue')
const assertionPicker = read('../src/components/JsonPathPickerDialog.vue')
const treeNode = read('../src/views/tools/TreeNode.vue')
const interfaces = read('../src/views/Interfaces.vue')
const interfaceEdit = read('../src/components/InterfaceEditDialog.vue')
const expressionInput = assertionPicker.match(/<el-input[\s\S]*?v-model="draft"[\s\S]*?\/>/)?.[0] || ''

for (const [operator, expected] of Object.entries({
  eq: '==',
  ne: '!=',
  neq: '!=',
  gt: '>',
  lt: '<',
  gte: '>=',
  lte: '<=',
  contains: '包含',
})) {
  assert.equal(getAssertionOperatorLabel(operator), expected)
}

for (const [name, source] of [
  ['测试报告执行结果', report],
  ['接口调试结果', debug],
]) {
  assert.match(source, /<AssertionDiffTable/, `${name}应复用统一的断言结果展示组件`)
  assert.doesNotMatch(
    source,
    /(?:eq|neq|gt|lt|gte|lte):\s*['"](?:等于|不等于|大于|小于|大于等于|小于等于)['"]/
  )
}

assert.match(assertionDisplay, /getAssertionOperatorLabel\(diff\.operator\)/, '断言结果组件应使用统一的断言操作符展示函数')
assert.match(assertionEditor, /@click="removeAssertion\(index\)"/, '删除按钮应按当前行直接删除断言')
assert.match(assertionEditor, /const removeAssertion = index => \{\s*props\.model\.assertions\.splice\(index, 1\)\s*\}/, '删除断言应直接从当前列表移除')
assert.doesNotMatch(assertionEditor, /assertion\?\.expression === '\$\.code'[\s\S]*?assertion\.enabled = false/, '删除断言不应被改成停用默认业务码断言')
assert.match(assertionEditor, /selection-mode/, '测试用例应使用按勾选结果同步的字段选择模式')
assert.match(assertionEditor, /:selected-assertions="model\.assertions"/, '字段选择弹窗应回显当前断言')
assert.match(assertionEditor, /@confirm-selection="applyPickedAssertionSelection"/, '字段选择弹窗应按勾选结果同步断言')
assert.match(assertionPicker, /const confirmSelection = \(\) =>/, '字段选择弹窗应统一提交勾选结果')
assert.match(assertionPicker, /emit\('confirm-selection', items\)/, '取消勾选后应允许提交空选择')
assert.match(assertionPicker, /selectedAssertionPaths = computed/, '字段选择弹窗应根据已有断言回显勾选状态')
assert.match(assertionPicker, /class="preview-tabs"/, '取值结果应按字段展示可切换的 Tab')
assert.match(assertionPicker, /class="preview-tab"/, '取值结果 Tab 应展示字段名称')
assert.match(assertionPicker, /@click="previousPreview"/, '取值结果应支持切换到上一个字段')
assert.match(assertionPicker, /@click="nextPreview"/, '取值结果应支持切换到下一个字段')
assert.match(assertionPicker, /const previewItems = computed/, '取值结果 Tab 应只对应已选字段节点')
assert.match(assertionPicker, /\.preview-tab\s*\{[\s\S]*?flex:\s*0 0 92px;/, '取值结果 Tab 应限制为紧凑固定宽度')
assert.match(assertionPicker, /\.preview-tab\.is-active\s*\{[\s\S]*?box-shadow:\s*inset 0 -2px/, '当前字段 Tab 应使用底部高亮线')
assert.match(assertionPicker, /\.preview-value\s*\{[\s\S]*?height:\s*132px;[\s\S]*?overflow:\s*auto;/, '取值区域应固定高度并内部滚动')
assert.match(assertionPicker, /v-if="awaitingManualFetch"[\s\S]*?v-else/, '请求前应只展示提示，请求后再展示结果与字段区域')
assert.match(expressionInput, /v-model="draft"[\s\S]*?readonly/, '字段表达式在选取弹窗中应只读')
assert.doesNotMatch(expressionInput, /clearable/, '只读表达式不应保留清空入口')
assert.match(assertionPicker, /class="manual-fetch-button"[^>]*type="primary"[^>]*link[^>]*@click="reload"/, '请求提示中的重新请求应使用明确的按钮样式')
assert.doesNotMatch(assertionPicker, /description="确认可以执行后/, '请求提示应使用可点击的重新请求按钮')
assert.doesNotMatch(assertionPicker, /class="preview-title"/, '取值结果区域不应重复展示标题')
assert.doesNotMatch(assertionPicker, /showResultTag|activePreviewFound/, '取值结果区域不应展示状态标签')
assert.match(assertionPicker, /class="picker-manual-fetch"[\s\S]*?<el-alert/, '请求前提示应放在独立的空状态面板中')
assert.match(assertionPicker, /<el-empty v-else-if="!loading && !errorText" description="暂无响应数据"/, '响应无数据时应使用统一空状态')
assert.match(assertionPicker, /\.picker-manual-fetch\s*\{[\s\S]*?border:\s*1px solid/, '请求前空状态面板应有完整边框')
assert.doesNotMatch(assertionPicker, /batchHint/, '字段选择弹窗底部不应继续展示对象或数组提示')
assert.match(treeNode, /class="node-content"[^>]*@click\.stop="handleContentClick"/, '字段内容区域应统一负责切换选中状态')
assert.match(treeNode, /@click\.stop="toggleExpanded"/, '展开箭头应独立处理收起和展开')
assert.match(treeNode, /<button[\s\S]*?v-if="hasChildren"/, '只有存在子字段时才展示展开按钮')
assert.match(treeNode, /<span v-else class="arrow-placeholder"/, '没有子字段时应保留内容对齐占位，不展示展开按钮')
assert.match(treeNode, /const handleContentClick = \(\) =>/, '字段内容点击应支持选中和取消选中')
assert.doesNotMatch(treeNode, /class="node-row"[\s\S]*?@click="handleRowClick"/, '字段整行不应再统一处理点击')
assert.match(treeNode, /const expanded = ref\(true\)/, '字段树打开时应默认展开')
assert.match(treeNode, /\.arrow\s*\{[\s\S]*?width:\s*28px;[\s\S]*?height:\s*28px;/, '展开箭头的样式和点击区域应适当放大')
assert.match(
  interfaceEdit,
  /<el-form-item label="服务标识"[^>]*class="nowrap-form-label"/,
  '服务标识标签不应换行'
)
assert.doesNotMatch(interfaces, /服务标识（可选）/, '服务标识标签不应继续展示“可选”')
assert.match(debug, /class="status-code-tag"/, '状态码应使用独立的窄标签样式')
assert.match(
  assertionEditor,
  /\.assertion-expression :deep\(\.el-input-group__append\)\s*\{[\s\S]*?border-top:\s*1px solid[\s\S]*?border-bottom:\s*1px solid/,
  '断言选取按钮所在的输入附加区应补齐上下边框'
)
assert.match(
  debug,
  /\.status-code-tag\s*\{[\s\S]*align-self:\s*flex-start[\s\S]*width:\s*fit-content/,
  '状态码标签应按内容收窄且不改变信息卡片列宽'
)

console.log('assertion display and UI constraints test ok')
